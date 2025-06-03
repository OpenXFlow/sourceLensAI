# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Command-line interface entry point for the sourceLens application.

Handles argument parsing, configuration loading, logging setup,
initial state preparation, and orchestration of the tutorial generation flow
for both codebases and web content using a modular flow-based architecture
with subcommands 'code' and 'web'.
"""

import argparse
import contextlib
import importlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Final, Optional, cast
from urllib.parse import urlparse

from typing_extensions import TypeAlias

from sourcelens.config_loader import (
    AUTO_DETECT_OUTPUT_NAME,
    ConfigDict,
    ConfigError,
    ConfigLoader,
)
from sourcelens.core import Flow as SourceLensFlow
from sourcelens.utils.helpers import sanitize_filename

if TYPE_CHECKING:  # pragma: no cover
    pass

SharedContextDict: TypeAlias = dict[str, Any]
ResolvedFlowConfigData: TypeAlias = ConfigDict

_DEFAULT_LOG_DIR_MAIN: Final[str] = "logs"
_DEFAULT_LOG_LEVEL_MAIN: Final[str] = "INFO"
_DEFAULT_LOG_FORMAT_MAIN: Final[str] = "%(asctime)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s"
_DEFAULT_WEB_OUTPUT_NAME_FALLBACK_MAIN: Final[str] = "web-content-analysis"
_DEFAULT_CODE_OUTPUT_NAME_FALLBACK_MAIN: Final[str] = "code-analysis-output"
_MAX_PROJECT_NAME_LEN_MAIN: Final[int] = 40
_DEFAULT_MAX_FILE_SIZE_MAIN: Final[int] = 150000
_DEFAULT_MAIN_OUTPUT_DIR_MAIN: Final[str] = "output"
_DEFAULT_GENERATED_TEXT_LANGUAGE_MAIN: Final[str] = "english"

logger_main: logging.Logger = logging.getLogger(__name__)

NoFilesFetchedError: Optional[type[Exception]] = None
try:
    # Corrected import path assuming FL01_code_analysis is a top-level directory in src
    # and nodes is a submodule. This structure implies FL01_code_analysis is effectively a package.
    n01_fetch_code_module_path = "FL01_code_analysis.nodes.n01_fetch_code"
    n01_fetch_code_module = importlib.import_module(n01_fetch_code_module_path)
    NoFilesFetchedError = getattr(n01_fetch_code_module, "NoFilesFetchedError", None)  # type: ignore[assignment]
    if NoFilesFetchedError is None:  # pragma: no cover

        class _PlaceholderNoFilesFetchedErrorNF(Exception):
            """Placeholder if original NoFilesFetchedError is not found."""

        NoFilesFetchedError = _PlaceholderNoFilesFetchedErrorNF
except ImportError:  # pragma: no cover

    class _MissingModuleForNoFilesFetchedErrorNF(Exception):
        """Placeholder if module for NoFilesFetchedError cannot be imported."""

    NoFilesFetchedError = _MissingModuleForNoFilesFetchedErrorNF
    logger_main.warning(
        "Could not dynamically import NoFilesFetchedError. Using a placeholder. "
        "This might affect specific error handling for no files fetched in code analysis."
    )


FLOW_MODULE_LOOKUP: Final[dict[str, tuple[str, str]]] = {
    "FL01_code_analysis": ("FL01_code_analysis.flow", "create_code_analysis_flow"),
    "FL02_web_crawling": ("FL02_web_crawling.flow", "create_web_crawling_flow"),
}
CLI_COMMAND_TO_INTERNAL_FLOW_MAP: Final[dict[str, str]] = {
    "code": "FL01_code_analysis",
    "code_analysis": "FL01_code_analysis",
    "web": "FL02_web_crawling",
    "web_crawling": "FL02_web_crawling",
}
CLI_FLOW_CHOICES: Final[list[str]] = list(CLI_COMMAND_TO_INTERNAL_FLOW_MAP.keys())


def _get_local_dir_display_root(local_dir: Optional[str]) -> str:
    """Return the display root for local directories, normalizing the path.

    Args:
        local_dir: The path string to the local directory.

    Returns:
        A normalized string representation of the local directory root.
    """
    if not local_dir or not isinstance(local_dir, str):
        return ""
    display_root_str: str = ""
    with contextlib.suppress(ValueError, TypeError, OSError):
        path_obj = Path(local_dir)
        if path_obj:
            display_root_str = path_obj.as_posix()
            if display_root_str == ".":
                display_root_str = "./"
            elif display_root_str and not display_root_str.endswith("/"):
                display_root_str += "/"
    return display_root_str


def setup_logging(log_config: dict[str, Any]) -> None:
    """Configure application-wide logging based on the provided configuration.

    Args:
        log_config: A dictionary containing logging configuration parameters.
    """
    log_dir_str: str = str(log_config.get("log_dir", _DEFAULT_LOG_DIR_MAIN))
    log_level_str: str = str(log_config.get("log_level", _DEFAULT_LOG_LEVEL_MAIN)).upper()
    log_level: int = getattr(logging, log_level_str, logging.INFO)
    log_file_path_from_config: Optional[str] = log_config.get("log_file")
    log_file_to_use: Optional[Path] = None

    if log_file_path_from_config and log_file_path_from_config.upper() != "NONE":
        log_file_to_use = Path(log_file_path_from_config)
    elif not log_file_path_from_config:  # Only set default if not "" and not "NONE"
        log_dir_path_obj = Path(log_dir_str)
        log_file_to_use = log_dir_path_obj / "sourcelens.log"

    handlers_to_add: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file_to_use:
        try:
            log_file_to_use.parent.mkdir(parents=True, exist_ok=True)
            handlers_to_add.append(logging.FileHandler(log_file_to_use, encoding="utf-8", mode="a"))
            logger_main.info("File logging enabled at: %s", log_file_to_use.resolve())
        except OSError as e_os_err:  # pragma: no cover
            print(f"ERROR: Failed to create log file at '{log_file_to_use}': {e_os_err}", file=sys.stderr)
            logger_main.error("File logging disabled due to setup error. Using console only.")
    else:
        logger_main.info("File logging is disabled.")

    logging.basicConfig(level=log_level, format=_DEFAULT_LOG_FORMAT_MAIN, handlers=handlers_to_add, force=True)
    logger_main.info("Logging initialized with level %s.", log_level_str)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the SourceLens tool using subparsers.

    Returns:
        An object containing the parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="SourceLens: Generate tutorials from codebases or web content using AI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default="config.json", metavar="FILE_PATH", help="Path to global config JSON file.")
    parser.add_argument(
        "-n", "--name", metavar="OUTPUT_NAME", help="Override default output name for the tutorial/summary."
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="MAIN_OUTPUT_DIR",
        type=Path,
        help="Override main output directory for generated files.",
    )
    parser.add_argument(
        "--language", metavar="LANG", help="Override generated text language (e.g., 'english', 'slovak')."
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override logging level from config.",
    )
    parser.add_argument(
        "--log-file",
        metavar="PATH_OR_NONE",
        help="Path to log file. Use 'NONE' to disable file logging if enabled by config.",
    )

    llm_overrides_group = parser.add_argument_group("LLM Overrides (common to all flows)")
    llm_overrides_group.add_argument(
        "--llm-provider", metavar="ID", help="Override active LLM provider ID from config."
    )
    llm_overrides_group.add_argument("--llm-model", metavar="NAME", help="Override LLM model name.")
    llm_overrides_group.add_argument("--api-key", metavar="KEY", help="Override LLM API key directly.")
    llm_overrides_group.add_argument("--base-url", metavar="URL", help="Override LLM API base URL.")

    subparsers = parser.add_subparsers(dest="flow_command", required=True, help="The type of analysis to perform.")

    code_parser = subparsers.add_parser(
        "code",
        aliases=["code_analysis"],
        help="Analyze source code from a repository or local directory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    code_source_group = code_parser.add_mutually_exclusive_group(required=True)
    code_source_group.add_argument("--dir", metavar="LOCAL_DIR", type=Path, help="Path to local codebase directory.")
    code_source_group.add_argument("--repo", metavar="REPO_URL", help="URL of the GitHub repository.")
    code_parser.add_argument("-i", "--include", nargs="+", metavar="PATTERN", help="Override include file patterns.")
    code_parser.add_argument("-e", "--exclude", nargs="+", metavar="PATTERN", help="Override exclude file patterns.")
    code_parser.add_argument("-s", "--max-size", type=int, metavar="BYTES", help="Override max file size (bytes).")
    code_parser.set_defaults(internal_flow_name="FL01_code_analysis")

    web_parser = subparsers.add_parser(
        "web",
        aliases=["web_crawling"],
        help="Crawl and analyze content from web URLs, sitemaps, or files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    web_source_group = web_parser.add_mutually_exclusive_group(required=True)
    web_source_group.add_argument("--crawl-url", metavar="WEB_URL", help="Root URL of a website to crawl.")
    web_source_group.add_argument("--crawl-sitemap", metavar="SITEMAP_URL", help="URL of a sitemap.xml to crawl.")
    web_source_group.add_argument(
        "--crawl-file", metavar="FILE_URL_OR_PATH", help="URL or local path to a single text/markdown file."
    )
    web_parser.add_argument("--crawl-depth", type=int, metavar="N", help="Override max crawl recursion depth.")
    web_parser.add_argument(
        "--crawl-output-subdir", metavar="NAME", help="Override subdir name for raw crawled web content."
    )
    web_parser.set_defaults(internal_flow_name="FL02_web_crawling")

    return parser.parse_args()


def _get_internal_flow_name(cli_flow_command: str) -> str:
    """Map CLI flow command to internal flow package name.

    Args:
        cli_flow_command: The flow command provided by the user via CLI.

    Returns:
        The corresponding internal flow name (e.g., "FL01_code_analysis").

    Raises:
        ValueError: If the `cli_flow_command` is not a recognized command.
    """
    internal_name = CLI_COMMAND_TO_INTERNAL_FLOW_MAP.get(cli_flow_command)
    if internal_name is None:  # Should not happen due to argparse choices
        raise ValueError(f"Unknown CLI flow command: {cli_flow_command}")  # pragma: no cover
    return internal_name


def _initialize_app_config_and_logging(args: argparse.Namespace) -> tuple[ResolvedFlowConfigData, str]:
    """Initialize configuration loader, resolve flow-specific config, and set up logging.

    Args:
        args: Parsed command-line arguments. `args.internal_flow_name` must be set.

    Returns:
        A tuple: (resolved_flow_config, internal_flow_name).
    """
    try:
        config_loader = ConfigLoader(str(args.config))
        internal_flow_name: str = args.internal_flow_name

        current_script_dir = Path(__file__).resolve().parent
        project_src_root = current_script_dir.parent
        flow_default_config_filename = "config.default.json"
        # Construct path to flow-specific default config relative to project structure
        # Assumes FL0X_... are directories at the same level as 'sourcelens' dir under 'src'
        flow_default_path = project_src_root / internal_flow_name / flow_default_config_filename

        if not flow_default_path.is_file():
            err_msg = f"Default config for flow '{internal_flow_name}' not found at: {flow_default_path}"
            print(f"CRITICAL ERROR: {err_msg}", file=sys.stderr)
            raise ConfigError(err_msg)

        resolved_flow_config: ResolvedFlowConfigData = config_loader.get_resolved_flow_config(
            flow_name=internal_flow_name,
            flow_default_config_path=flow_default_path,
            cli_args=args,
        )

        common_config_final: dict[str, Any] = resolved_flow_config.get("common", {})
        logging_settings_final: dict[str, Any] = common_config_final.get("logging", {})
        if args.log_file is not None:  # Honor CLI override for log_file path or NONE
            logging_settings_final["log_file"] = str(args.log_file)

        setup_logging(logging_settings_final)

        log_msg_main = "Global and flow-specific configuration loaded and processed successfully for flow: %s"
        logger_main.info(log_msg_main, internal_flow_name)
        return resolved_flow_config, internal_flow_name

    except ConfigError as e_conf:
        print(f"ERROR: Configuration setup failed: {e_conf!s}", file=sys.stderr)
        if not logger_main.handlers:  # pragma: no cover
            logging.basicConfig(level=logging.ERROR, format=_DEFAULT_LOG_FORMAT_MAIN, stream=sys.stderr)
        logger_main.critical("Configuration error: %s", e_conf, exc_info=True)
        sys.exit(1)
    except (FileNotFoundError, ValueError) as e_file_val:  # pragma: no cover
        print(f"ERROR: File or value error during config setup: {e_file_val!s}", file=sys.stderr)
        if not logger_main.handlers:
            logging.basicConfig(level=logging.ERROR, format=_DEFAULT_LOG_FORMAT_MAIN, stream=sys.stderr)
        logger_main.critical("File/Value error during config: %s", e_file_val, exc_info=True)
        sys.exit(1)
    except (ImportError, AttributeError, RuntimeError, OSError) as e_unexpected:  # pragma: no cover
        print(f"ERROR: Unexpected error during app initialization: {e_unexpected!s}", file=sys.stderr)
        if not logger_main.handlers:
            logging.basicConfig(level=logging.ERROR, format=_DEFAULT_LOG_FORMAT_MAIN, stream=sys.stderr)
        logger_main.critical("Unexpected initialization error: %s", e_unexpected, exc_info=True)
        sys.exit(1)


# --- Name Derivation Functions ---
def _derive_name_from_web_source(args: argparse.Namespace) -> str:
    """Derive an output name specifically for web sources.

    Args:
        args: Parsed command-line arguments.

    Returns:
        A derived name for web analysis.
    """
    source_val: Any = args.crawl_url or args.crawl_sitemap or args.crawl_file
    name_candidate: str = ""

    if source_val:
        source_str = str(source_val)
        try:
            parsed_url_obj = urlparse(source_str)
            # If it has a scheme and netloc, it's likely a URL
            if parsed_url_obj.scheme and parsed_url_obj.netloc:
                name_candidate = parsed_url_obj.netloc or Path(parsed_url_obj.path).stem or ""
            else:  # Otherwise, treat as a file path
                name_candidate = Path(source_str).stem
            if name_candidate:
                return sanitize_filename(name_candidate, max_len=_MAX_PROJECT_NAME_LEN_MAIN)
        except (ValueError, TypeError, AttributeError, OSError) as e:  # More specific exceptions
            logger_main.warning("Could not derive name from web source '%s': %s", source_str, e)
    return _DEFAULT_WEB_OUTPUT_NAME_FALLBACK_MAIN


def _derive_name_from_code_source(args: argparse.Namespace) -> str:
    """Derive an output name specifically for code sources.

    Args:
        args: Parsed command-line arguments.

    Returns:
        A derived name for code analysis.
    """
    repo_url_val: Any = args.repo
    local_dir_val: Any = args.dir
    repo_url: Optional[str] = str(repo_url_val) if isinstance(repo_url_val, str) else None
    local_dir_path: Optional[Path] = local_dir_val if isinstance(local_dir_val, Path) else None
    name_candidate: str = ""

    if repo_url:
        with contextlib.suppress(ValueError, TypeError, AttributeError, OSError, IndexError):
            parsed_url_obj = urlparse(repo_url)
            if parsed_url_obj.path:
                name_part = parsed_url_obj.path.strip("/").split("/")[-1]
                name_candidate = name_part.removesuffix(".git")
    elif local_dir_path:
        with contextlib.suppress(OSError, ValueError, TypeError):
            name_candidate = local_dir_path.name
    return (
        sanitize_filename(name_candidate, max_len=_MAX_PROJECT_NAME_LEN_MAIN)
        if name_candidate
        else _DEFAULT_CODE_OUTPUT_NAME_FALLBACK_MAIN
    )


def _derive_name_from_source_if_auto(args: argparse.Namespace, config_output_name: str, internal_flow_name: str) -> str:
    """Derive the output name from source if config_output_name is 'auto-generated'.

    Args:
        args: Parsed command-line arguments.
        config_output_name: The output name from the configuration.
        internal_flow_name: The internal name of the flow being run.

    Returns:
        The final output name.
    """
    if config_output_name != AUTO_DETECT_OUTPUT_NAME:
        return config_output_name

    if args.name:
        return str(args.name)

    derived_name: str
    if internal_flow_name == "FL01_code_analysis":
        derived_name = _derive_name_from_code_source(args)
    elif internal_flow_name == "FL02_web_crawling":
        derived_name = _derive_name_from_web_source(args)
    else:  # pragma: no cover
        logger_main.warning("Unknown flow_name '%s' for name derivation. Using generic fallback.", internal_flow_name)
        derived_name = "unknown_flow_output"

    if not derived_name:  # pragma: no cover
        logger_main.error("Name derivation failed unexpectedly, using generic flow-based fallback.")
        derived_name = (
            _DEFAULT_CODE_OUTPUT_NAME_FALLBACK_MAIN
            if internal_flow_name == "FL01_code_analysis"
            else _DEFAULT_WEB_OUTPUT_NAME_FALLBACK_MAIN
        )
    return derived_name


def _prepare_runtime_initial_context(  # noqa: C901
    args: argparse.Namespace, resolved_flow_config: ResolvedFlowConfigData, internal_flow_name: str
) -> SharedContextDict:
    """Prepare the initial shared context for the specific flow to be run.

    Args:
        args: Parsed command-line arguments.
        resolved_flow_config: The fully resolved configuration for the current flow.
        internal_flow_name: The internal name of the flow being executed.

    Returns:
        The initial_context dictionary for the pipeline.
    """
    logger_main.debug("Preparing initial_context for flow: %s", internal_flow_name)

    common_settings: dict[str, Any] = resolved_flow_config.get("common", {})
    common_output_settings: dict[str, Any] = common_settings.get("common_output_settings", {})

    output_name_from_config = str(common_output_settings.get("default_output_name", AUTO_DETECT_OUTPUT_NAME))
    final_output_name = _derive_name_from_source_if_auto(args, output_name_from_config, internal_flow_name)

    main_out_dir_from_config = str(common_output_settings.get("main_output_directory", _DEFAULT_MAIN_OUTPUT_DIR_MAIN))
    final_main_out_dir = str(args.output) if args.output else main_out_dir_from_config

    gen_text_lang_from_config = str(
        common_output_settings.get("generated_text_language", _DEFAULT_GENERATED_TEXT_LANGUAGE_MAIN)
    )
    final_gen_text_lang = str(args.language) if args.language else gen_text_lang_from_config

    flow_specific_config_block: dict[str, Any] = resolved_flow_config.get(internal_flow_name, {})

    initial_context: SharedContextDict = {
        "config": resolved_flow_config,
        "llm_config": resolved_flow_config.get("resolved_llm_config", {}),
        "cache_config": common_settings.get("cache_settings", {}),
        "project_name": final_output_name,
        "output_dir": final_main_out_dir,
        "language": final_gen_text_lang,
        "current_operation_mode": internal_flow_name,
        "current_mode_output_options": flow_specific_config_block.get("output_options", {}),
    }

    if args.internal_flow_name == "FL01_code_analysis":
        initial_context.update(
            {
                "repo_url": args.repo,
                "local_dir": str(args.dir) if args.dir else None,
                "local_dir_display_root": _get_local_dir_display_root(str(args.dir)) if args.dir else "",
                "source_config": flow_specific_config_block.get("source_config", {}),
                "github_token": flow_specific_config_block.get("resolved_github_token"),
                "include_patterns": set(
                    args.include or flow_specific_config_block.get("source_options", {}).get("include_patterns", [])
                ),
                "exclude_patterns": set(
                    args.exclude
                    or flow_specific_config_block.get("source_options", {}).get("default_exclude_patterns", [])
                ),
                "max_file_size": args.max_size
                if args.max_size is not None
                else flow_specific_config_block.get("source_options", {}).get(
                    "max_file_size_bytes", _DEFAULT_MAX_FILE_SIZE_MAIN
                ),
                "use_relative_paths": bool(
                    flow_specific_config_block.get("source_options", {}).get("use_relative_paths", True)
                ),
            }
        )
    elif args.internal_flow_name == "FL02_web_crawling":
        crawl_file_val: Any = args.crawl_file
        crawl_file_final: Optional[str] = None
        if crawl_file_val:
            crawl_file_str = str(crawl_file_val)
            try:
                p_crawl_file = Path(crawl_file_str)
                is_likely_path = os.sep in crawl_file_str or (os.path.altsep and os.path.altsep in crawl_file_str)
                if not urlparse(crawl_file_str).scheme and (
                    p_crawl_file.is_file() or (is_likely_path and not p_crawl_file.exists())
                ):
                    crawl_file_final = str(p_crawl_file.resolve())
                else:
                    crawl_file_final = crawl_file_str
            except (ValueError, TypeError, OSError) as e_path:  # pragma: no cover
                logger_main.warning(
                    "Could not definitively resolve --crawl-file '%s' as local path: %s. Treating as string.",
                    crawl_file_str,
                    e_path,
                )
                crawl_file_final = crawl_file_str

        initial_context.update(
            {
                "crawl_url": args.crawl_url,
                "crawl_sitemap": args.crawl_sitemap,
                "crawl_file": crawl_file_final,
                # These overrides are now correctly pulled from flow_specific_config_block
                # which gets them from resolved_flow_config (already merged with CLI args)
                "cli_crawl_depth": flow_specific_config_block.get("crawler_options", {}).get("max_depth_recursive"),
                "cli_crawl_output_subdir": flow_specific_config_block.get("crawler_options", {}).get(
                    "default_output_subdir_name"
                ),
            }
        )

    placeholders: dict[str, Any] = {
        "files": [],
        "text_concepts": [],
        "abstractions": [],
        "text_relationships": {},
        "relationships": {},
        "text_chapter_order": [],
        "chapter_order": [],
        "identified_scenarios": [],
        "text_chapters": [],
        "chapters": [],
        "source_index_content": None,
        "project_review_content": None,
        "content_inventory_md": None,
        "web_content_review_md": None,
        "final_output_dir": None,
        "final_output_dir_web_crawl": None,
        "relationship_flowchart_markup": None,
        "class_diagram_markup": None,
        "package_diagram_markup": None,
        "file_structure_diagram_markup": None,
        "sequence_diagrams_markup": [],
    }
    for key, default_val in placeholders.items():
        initial_context.setdefault(key, default_val)

    logger_main.debug(
        "Runtime initial context prepared for flow '%s'. Project name: '%s'", internal_flow_name, final_output_name
    )
    if logger_main.isEnabledFor(logging.DEBUG):  # pragma: no cover
        try:
            log_context_copy = json.loads(json.dumps(initial_context))
            if "llm_config" in log_context_copy and isinstance(log_context_copy["llm_config"], dict):
                log_context_copy["llm_config"]["api_key"] = "***REDACTED***"
            if "github_token" in log_context_copy:
                log_context_copy["github_token"] = "***REDACTED***"
            logger_main.debug("Full initial_context (redacted): %s", json.dumps(log_context_copy, indent=2))
        except (TypeError, ValueError) as e_json_dump:
            logger_main.debug("Could not serialize initial_context for debug logging: %s", e_json_dump)
    return initial_context


def _get_flow_creator_function(internal_flow_name: str) -> Callable[[SharedContextDict], SourceLensFlow]:
    """Dynamically import and retrieve the flow creation function.

    Args:
        internal_flow_name: The internal name of the flow (e.g., "FL01_code_analysis").

    Returns:
        The callable function (e.g., `create_code_analysis_flow`).
    """
    logger_main.debug("Attempting to get flow creator for internal flow: %s", internal_flow_name)
    if internal_flow_name not in FLOW_MODULE_LOOKUP:  # pragma: no cover
        supported_keys = list(FLOW_MODULE_LOOKUP.keys())
        raise ValueError(f"Internal flow '{internal_flow_name}' is not supported. Supported: {supported_keys}")

    module_path_str, creator_func_name = FLOW_MODULE_LOOKUP[internal_flow_name]

    try:
        # Ensure that import paths are relative to the 'src' directory if needed
        # by making sure the top-level package 'sourcelens' and sibling flow packages
        # like 'FL01_code_analysis' are correctly discoverable.
        # This often means running python from the directory above 'src', or having 'src' in PYTHONPATH.
        module = importlib.import_module(module_path_str)
        logger_main.info("Successfully imported module: %s", module_path_str)
    except ImportError as e_import_err:  # pragma: no cover
        logger_main.error("Failed to import module %s: %s", module_path_str, e_import_err)
        error_msg = (
            f"Could not import module '{module_path_str}' for internal flow '{internal_flow_name}'. "
            "Ensure the flow package is correctly installed and accessible in PYTHONPATH. "
            "Try running from the project root directory."
        )
        raise ImportError(error_msg) from e_import_err

    try:
        creator_func = cast(Callable[[SharedContextDict], SourceLensFlow], getattr(module, creator_func_name))
        logger_main.info(
            "Successfully retrieved creator function: %s from %s",
            creator_func_name,
            module_path_str,
        )
        return creator_func
    except AttributeError as e_attr_err:  # pragma: no cover
        logger_main.error(
            "Creator function %s not found in module %s: %s",
            creator_func_name,
            module_path_str,
            e_attr_err,
        )
        error_msg = (
            f"Creator function '{creator_func_name}' not found in "
            f"module '{module_path_str}' for internal flow '{internal_flow_name}'."
        )
        raise ValueError(error_msg) from e_attr_err


def _log_run_flow_startup_info(initial_context: SharedContextDict, internal_flow_name: str) -> None:
    """Log essential startup information before running the processing flow.

    Args:
        initial_context: The prepared shared context.
        internal_flow_name: The internal name of the flow being run.
    """
    source_description: str = "N/A"
    if internal_flow_name == "FL01_code_analysis":
        source_val = initial_context.get("repo_url") or initial_context.get("local_dir")
        source_description = str(source_val) if source_val is not None else "N/A"
        logger_main.info("Starting code analysis for: %s", source_description)
        code_source_cfg: dict[str, Any] = initial_context.get("source_config", {})
        lang_name = code_source_cfg.get("language_name_for_llm", "N/A")
        parser_type = code_source_cfg.get("parser_type", "N/A")
        logger_main.info("Active Code Language Profile: %s (Parser: %s)", lang_name, parser_type)
    elif internal_flow_name == "FL02_web_crawling":
        source_val = (
            initial_context.get("crawl_url")
            or initial_context.get("crawl_sitemap")
            or initial_context.get("crawl_file")
        )
        source_description = str(source_val) if source_val is not None else "N/A"
        logger_main.info("Starting web content analysis for: %s", source_description)
    else:  # pragma: no cover
        logger_main.error("Unknown internal flow name '%s' for startup info logging.", internal_flow_name)

    logger_main.info("Output Name for this run: %s", initial_context.get("project_name"))
    logger_main.info("Main Output Directory Base: %s", initial_context.get("output_dir"))
    logger_main.info("Generated Text Language: %s", initial_context.get("language"))

    llm_cfg_for_log: dict[str, Any] = initial_context.get("llm_config", {})
    provider = llm_cfg_for_log.get("provider", "N/A")
    llm_type = "local" if llm_cfg_for_log.get("is_local_llm") else "cloud"
    model = llm_cfg_for_log.get("model", "N/A")
    logger_main.info(f"Active LLM Provider for flow '{internal_flow_name}': {provider} ({llm_type})")
    logger_main.info(f"Active LLM Model for flow '{internal_flow_name}': {model}")


def _check_operation_mode_enabled(internal_flow_name: str, resolved_config: ResolvedFlowConfigData) -> None:
    """Verify if the determined flow is enabled in the configuration.

    Args:
        internal_flow_name: The internal name of the flow (e.g., "FL01_code_analysis").
        resolved_config: The fully resolved configuration for this specific flow.
    """
    flow_specific_settings: dict[str, Any] = resolved_config.get(internal_flow_name, {})
    is_enabled: bool = bool(flow_specific_settings.get("enabled", False))

    if not is_enabled:
        msg = (
            f"Flow '{internal_flow_name}' is disabled in the configuration (expected "
            f"'{internal_flow_name}.enabled=true'). Halting execution."
        )
        logger_main.error(msg)
        print(f"\n❌ ERROR: {msg}", file=sys.stderr)
        sys.exit(1)


def _validate_flow_output_or_exit(initial_context: SharedContextDict, internal_flow_name: str) -> None:
    """Validate if essential output was generated by the flow; exit if not.

    Args:
        initial_context: The shared context after the flow has run.
        internal_flow_name: The internal name of the flow that was run.
    """
    if internal_flow_name == "FL01_code_analysis":  # pragma: no cover
        # Code analysis flow validation might check `final_output_dir` or `chapters`
        pass
    elif internal_flow_name == "FL02_web_crawling":
        web_files_populated = bool(initial_context.get("files"))
        raw_crawl_output_dir_set = bool(initial_context.get("final_output_dir_web_crawl"))

        # Get processing_mode from the resolved_config stored in initial_context
        resolved_flow_config: ResolvedFlowConfigData = cast(ResolvedFlowConfigData, initial_context.get("config", {}))
        web_flow_settings: dict[str, Any] = resolved_flow_config.get(internal_flow_name, {})
        crawler_opts: dict[str, Any] = web_flow_settings.get("crawler_options", {})
        processing_mode_web = str(crawler_opts.get("processing_mode", "minimalistic"))

        essential_output_missing = False
        if processing_mode_web == "llm_extended" and not web_files_populated:
            essential_output_missing = True
            msg1 = "Halting: No web content in shared_context['files'] for LLM analysis "
            msg2 = "after FetchWebPage (llm_extended mode)."
            logger_main.error(msg1 + msg2)
        elif processing_mode_web == "minimalistic" and not raw_crawl_output_dir_set:
            # In minimalistic mode, we only expect FetchWebPage to run and set
            # final_output_dir_web_crawl. If it's not set, something went wrong.
            essential_output_missing = True
            logger_main.error("Halting: Raw crawl output directory not set after FetchWebPage (minimalistic mode).")

        if essential_output_missing:  # pragma: no cover
            err_msg_l1 = "\n❌ ERROR: No web content was successfully fetched or processed for the selected mode."
            err_msg_l2_parts = [
                "       Please check the target URL/sitemap, network connection, ",
                "and crawler/configuration options.",
            ]
            print(err_msg_l1, file=sys.stderr)
            print("".join(err_msg_l2_parts), file=sys.stderr)
            sys.exit(1)


def _handle_flow_completion(initial_context: SharedContextDict, internal_flow_name: str) -> None:
    """Handle logging and printing messages after the main processing flow completes.

    Args:
        initial_context: The shared context after flow execution.
        internal_flow_name: The internal name of the flow that was run.
    """
    final_dir_main_output_any: Any = initial_context.get("final_output_dir")
    final_output_path_confirmed: Optional[Path] = None
    msg_type: str = "Analysis"

    if final_dir_main_output_any and isinstance(final_dir_main_output_any, str):
        final_output_path_confirmed = Path(final_dir_main_output_any)
        msg_type = "Web summary/tutorial" if internal_flow_name == "FL02_web_crawling" else "Code tutorial"
    elif internal_flow_name == "FL02_web_crawling":
        # If main output dir isn't set by CombineWebSummary (e.g. minimalistic mode),
        # use the raw crawl output dir set by FetchWebPage
        final_dir_crawl_raw_any: Any = initial_context.get("final_output_dir_web_crawl")
        if final_dir_crawl_raw_any and isinstance(final_dir_crawl_raw_any, str):
            final_output_path_confirmed = Path(final_dir_crawl_raw_any)
            msg_part1 = "Raw crawled web content (summary/tutorial generation "
            msg_part2 = "may have been skipped or failed)"
            msg_type = msg_part1 + msg_part2
        else:  # pragma: no cover
            err_msg = "Web flow finished, but no output directory was confirmed for raw or summarized content."
            logger_main.error(err_msg)
    else:  # pragma: no cover
        logger_main.error("Code analysis flow finished, but 'final_output_dir' was not set in shared_context.")

    if final_output_path_confirmed and final_output_path_confirmed.exists() and final_output_path_confirmed.is_dir():
        resolved_path_str = str(final_output_path_confirmed.resolve())
        logger_main.info("%s processing completed. Output in: %s", msg_type.capitalize(), resolved_path_str)
        print(f"\n✅ {msg_type.capitalize()} processing complete! Files are in: {resolved_path_str}")
        return

    log_msg_fail = "Flow finished, but a valid final output directory was not confirmed or found."
    print(f"\n⚠️ ERROR: {log_msg_fail}", file=sys.stderr)  # pragma: no cover
    logger_main.error(log_msg_fail + f" (Flow: {internal_flow_name})")  # pragma: no cover
    sys.exit(1)  # pragma: no cover


def _run_flow(initial_context: SharedContextDict, internal_flow_name: str) -> None:
    """Instantiate and execute the appropriate processing flow.

    Args:
        initial_context: The prepared initial shared context for the flow.
        internal_flow_name: The internal name of the flow to run.
    """
    _check_operation_mode_enabled(internal_flow_name, cast(ResolvedFlowConfigData, initial_context.get("config", {})))
    _log_run_flow_startup_info(initial_context, internal_flow_name)

    processing_flow: Optional[SourceLensFlow] = None
    try:
        create_flow_function: Callable[[SharedContextDict], SourceLensFlow] = _get_flow_creator_function(
            internal_flow_name
        )
        processing_flow = create_flow_function(initial_context)
        logger_main.info("Pipeline for flow '%s' created successfully.", internal_flow_name)
    except (ImportError, ValueError, AttributeError) as e_create_flow:  # pragma: no cover
        logger_main.critical(
            "Failed to create pipeline for flow '%s': %s", internal_flow_name, e_create_flow, exc_info=True
        )
        sys.exit(1)

    if not processing_flow:  # pragma: no cover
        logger_main.error("Pipeline for flow '%s' could not be instantiated. Halting.", internal_flow_name)
        sys.exit(1)

    try:
        logger_main.info("Running the %s pipeline...", internal_flow_name)
        processing_flow.run_standalone(initial_context)
        _validate_flow_output_or_exit(initial_context, internal_flow_name)
        _handle_flow_completion(initial_context, internal_flow_name)

    except (ConfigError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, OSError, ImportError) as e_flow:
        if (
            internal_flow_name == "FL01_code_analysis"
            and NoFilesFetchedError is not None  # Ensure NoFilesFetchedError is not None
            and isinstance(e_flow, NoFilesFetchedError)
        ):
            logger_main.error(
                "No files fetched during code analysis flow: %s. This is a critical error.", e_flow, exc_info=False
            )
            print(f"\n❌ CRITICAL ERROR: No source files were found for analysis. Details: {e_flow}", file=sys.stderr)
            sys.exit(1)
        else:  # pragma: no cover
            logger_main.critical("Error during %s pipeline execution: %s", internal_flow_name, e_flow, exc_info=True)
            print(f"\n❌ ERROR: Pipeline execution failed: {e_flow!s}", file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:  # pragma: no cover
        logger_main.warning("Execution interrupted by user (KeyboardInterrupt).")
        print("\n❌ Execution interrupted by user.", file=sys.stderr)
        sys.exit(130)


def main() -> None:
    """Run the main command-line entry point for the SourceLens application."""
    args: argparse.Namespace = parse_arguments()
    resolved_flow_config, internal_flow_name_to_run = _initialize_app_config_and_logging(args)
    initial_shared_context: SharedContextDict = _prepare_runtime_initial_context(
        args, resolved_flow_config, internal_flow_name_to_run
    )
    _run_flow(initial_shared_context, internal_flow_name_to_run)


if __name__ == "__main__":  # pragma: no cover
    main()

# End of src/sourcelens/main.py
