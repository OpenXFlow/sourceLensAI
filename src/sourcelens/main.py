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
for both codebases and web content.
"""

import argparse
import contextlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional  # Removed Set import
from urllib.parse import urlparse

from typing_extensions import TypeAlias

from sourcelens.config import ConfigError, load_config
from sourcelens.flow import create_tutorial_flow
from sourcelens.utils.helpers import sanitize_filename

jsonschema: Optional[Any] = None
JSONSCHEMA_AVAILABLE = False
try:
    import jsonschema as imported_jsonschema

    jsonschema = imported_jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    pass

if TYPE_CHECKING:
    from sourcelens.core.flow_engine_sync import Flow as SourceLensFlow

SharedContextDict: TypeAlias = dict[str, Any]
ConfigDict: TypeAlias = dict[str, Any]

DEFAULT_LOG_DIR_MAIN: str = "logs"
DEFAULT_LOG_FORMAT: str = "%(asctime)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s"
DEFAULT_WEB_PROJECT_NAME: str = "web-content-analysis"
MAX_PROJECT_NAME_LEN_FROM_URL: int = 40


def setup_logging(log_config: dict[str, Any]) -> None:
    """Configure application-wide logging.

    Sets up logging to both a file (`sourcelens.log` in the configured
    log directory) and to standard output. The logging level and format
    are determined by the provided configuration or defaults.

    Args:
        log_config (dict[str, Any]): A dictionary containing logging configuration parameters,
                                     typically extracted from the main application config.
                                     Expected keys: 'log_dir' (str), 'log_level' (str).
    """
    log_dir_str: str = str(log_config.get("log_dir", DEFAULT_LOG_DIR_MAIN))
    log_level_str: str = str(log_config.get("log_level", "INFO")).upper()
    log_level: int = getattr(logging, log_level_str, logging.INFO)
    log_dir: Path = Path(log_dir_str)
    log_file: Optional[Path] = None

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "sourcelens.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        stream_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        logging.basicConfig(
            level=log_level,
            format=DEFAULT_LOG_FORMAT,
            handlers=[file_handler, stream_handler],
            force=True,
        )
        logging.getLogger(__name__).info("Logging initialized. Log file: %s", log_file.resolve() if log_file else "N/A")
    except OSError as e:
        print(f"ERROR: Failed create log dir/file '{log_file or log_dir}': {e}", file=sys.stderr)
        logging.basicConfig(
            level=log_level,
            format=DEFAULT_LOG_FORMAT,
            handlers=[logging.StreamHandler(sys.stdout)],
            force=True,
        )
        logging.getLogger(__name__).error("File logging disabled due to setup error. Logging to stdout only.")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the SourceLens tool.

    Defines arguments for specifying the source (local directory, GitHub repo,
    or web URL/sitemap/file), configuration file, and various overrides for
    output, filtering, and web crawling behavior.

    Returns:
        argparse.Namespace: An object containing the parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="SourceLens: Generate tutorials from codebases or web content using AI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    source_type_group = parser.add_mutually_exclusive_group(required=True)
    source_type_group.add_argument("--repo", metavar="REPO_URL", help="URL of the GitHub repository to analyze.")
    source_type_group.add_argument("--dir", metavar="LOCAL_DIR", help="Path to local codebase directory to analyze.")
    source_type_group.add_argument("--crawl-url", metavar="WEB_URL", help="Root URL of a website to crawl.")
    source_type_group.add_argument("--crawl-sitemap", metavar="SITEMAP_URL", help="URL of a sitemap.xml to crawl.")
    source_type_group.add_argument(
        "--crawl-file", metavar="FILE_URL_OR_PATH", help="URL or local path to a single text/markdown file."
    )
    parser.add_argument("--config", default="config.json", metavar="FILE_PATH", help="Path to config JSON file.")
    parser.add_argument("-n", "--name", metavar="PROJECT_NAME", help="Override project name.")
    parser.add_argument("-o", "--output", metavar="OUTPUT_DIR", help="Override base output directory from config.")
    code_group = parser.add_argument_group("Code Analysis Options")
    code_group.add_argument("-i", "--include", nargs="+", metavar="PATTERN", help="Override include patterns.")
    code_group.add_argument("-e", "--exclude", nargs="+", metavar="PATTERN", help="Override exclude patterns.")
    code_group.add_argument("-s", "--max-size", type=int, metavar="BYTES", help="Override max file size.")
    code_group.add_argument("--language", metavar="LANG", help="Override tutorial output language.")
    crawl_group = parser.add_argument_group("Web Crawling Options")
    crawl_group.add_argument("--crawl-depth", type=int, metavar="N", help="Max crawl recursion depth.")
    crawl_group.add_argument("--crawl-output-subdir", metavar="NAME", help="Subdir for crawled web content.")
    return parser.parse_args()


def _get_project_name(args: argparse.Namespace, project_config: dict[str, Any]) -> Optional[str]:
    """Determine the project name from CLI args or project config.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        project_config (dict[str, Any]): 'project' section of the application configuration.

    Returns:
        Optional[str]: The determined project name, or None if not found.
    """
    project_name_override: Optional[str] = args.name if isinstance(args.name, str) else None
    if project_name_override:
        return project_name_override
    project_name_cfg_val: Any = project_config.get("default_name")
    return str(project_name_cfg_val) if isinstance(project_name_cfg_val, str) else None


def _derive_web_project_name(args: argparse.Namespace, existing_name: Optional[str]) -> str:
    """Derive project name for web crawls if not already set.

    If an `existing_name` is provided, it is returned. Otherwise, attempts to
    derive a name from the crawl URL arguments. If derivation fails,
    `DEFAULT_WEB_PROJECT_NAME` is used.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        existing_name (Optional[str]): A pre-existing project name (e.g., from --name).

    Returns:
        str: The derived or default project name for a web crawl.
    """
    if existing_name:
        return existing_name
    crawl_source_url: Optional[str] = args.crawl_url or args.crawl_sitemap or args.crawl_file
    if crawl_source_url and isinstance(crawl_source_url, str):
        with contextlib.suppress(ValueError, TypeError, AttributeError, OSError):
            parsed_url = urlparse(crawl_source_url)
            name_candidate: str = parsed_url.netloc or Path(parsed_url.path).stem or ""
            if name_candidate:
                return sanitize_filename(str(name_candidate), max_len=MAX_PROJECT_NAME_LEN_FROM_URL)
    return DEFAULT_WEB_PROJECT_NAME


def _get_path_patterns(args: argparse.Namespace, source_config: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Get include and exclude path patterns from CLI args and configuration.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        source_config (dict[str, Any]): 'source' section of the application configuration.

    Returns:
        tuple[set[str], set[str]]: A tuple containing the set of include patterns
                                   and the set of exclude patterns.
    """
    cli_include: Optional[list[str]] = args.include if isinstance(args.include, list) else None
    config_include: list[str] = source_config.get("default_include_patterns", [])
    include_patterns: set[str] = {str(p) for p in (cli_include or config_include) if isinstance(p, str)}

    cli_exclude: Optional[list[str]] = args.exclude if isinstance(args.exclude, list) else None
    config_exclude: list[str] = source_config.get("default_exclude_patterns", [])
    exclude_patterns: set[str] = {str(p) for p in (cli_exclude or config_exclude) if isinstance(p, str)}
    return include_patterns, exclude_patterns


def _get_max_file_size(args: argparse.Namespace, source_config: dict[str, Any]) -> Optional[int]:
    """Get the maximum file size from CLI args or configuration.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        source_config (dict[str, Any]): 'source' section of the application configuration.

    Returns:
        Optional[int]: The maximum file size in bytes, or None if not specified.
    """
    if args.max_size is not None and isinstance(args.max_size, int):
        return int(args.max_size)
    max_size_cfg: Any = source_config.get("max_file_size_bytes")
    if isinstance(max_size_cfg, int):  # Check for int first
        return max_size_cfg
    if isinstance(max_size_cfg, float) and max_size_cfg.is_integer():
        return int(max_size_cfg)
    return None


def _get_local_dir_display_root(local_dir: Optional[str]) -> str:
    """Get the display root for local directories, normalizing the path.

    Args:
        local_dir (Optional[str]): The path to the local directory.

    Returns:
        str: A normalized string representation of the local directory root,
             ending with a slash, or an empty string if `local_dir` is None or invalid.
    """
    if not local_dir or not isinstance(local_dir, str):
        return ""
    display_root_str: str = ""
    with contextlib.suppress(ValueError, TypeError, OSError):
        path_obj = Path(local_dir)
        display_root_str = path_obj.as_posix()
        if display_root_str == ".":
            display_root_str = "./"
        elif not display_root_str.endswith("/"):
            display_root_str += "/"
    return display_root_str


def _prepare_initial_context(args: argparse.Namespace, config: ConfigDict) -> SharedContextDict:
    """Prepare the initial shared context dictionary for the processing flow.

    Consolidates settings from config and CLI args. Sets up placeholders for
    data generated by nodes.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        config (ConfigDict): The loaded application configuration.

    Returns:
        SharedContextDict: The initialized shared context.
    """
    source_cfg: dict[str, Any] = config.get("source", {})
    output_cfg: dict[str, Any] = config.get("output", {})
    project_cfg: dict[str, Any] = config.get("project", {})

    project_name_override: Optional[str] = _get_project_name(args, project_cfg)
    is_web_crawl = bool(args.crawl_url or args.crawl_sitemap or args.crawl_file)
    final_project_name: Optional[str] = (
        _derive_web_project_name(args, project_name_override) if is_web_crawl else project_name_override
    )

    include_patterns, exclude_patterns = _get_path_patterns(args, source_cfg)
    max_file_size = _get_max_file_size(args, source_cfg)
    local_dir_path: Optional[str] = args.dir if isinstance(args.dir, str) else None
    local_dir_display_root = _get_local_dir_display_root(local_dir_path)

    output_dir_val: Any = args.output or output_cfg.get("base_dir", "output")
    language_val: Any = args.language or output_cfg.get("language", "english")
    github_token_val: Any = config.get("github", {}).get("token")

    initial_context: SharedContextDict = {
        "config": config,
        "llm_config": config.get("llm", {}),
        "cache_config": config.get("cache", {}),
        "project_name_override": project_name_override,
        "project_name": final_project_name,
        "output_dir": str(output_dir_val),
        "language": str(language_val),
        "crawl_url": args.crawl_url,
        "crawl_sitemap": args.crawl_sitemap,
        "crawl_file": args.crawl_file,
        "cli_crawl_depth": args.crawl_depth,
        "cli_crawl_output_subdir": args.crawl_output_subdir,
        "repo_url": args.repo,
        "local_dir": local_dir_path,
        "source_config": source_cfg,
        "github_token": str(github_token_val) if github_token_val is not None else None,
        "include_patterns": include_patterns,
        "exclude_patterns": exclude_patterns,
        "max_file_size": max_file_size,
        "use_relative_paths": bool(source_cfg.get("use_relative_paths", True)),
        "local_dir_display_root": local_dir_display_root,
        "files": [],
        "abstractions": [],
        "relationships": {},
        "chapter_order": [],
        "identified_scenarios": [],
        "chapters": [],
        "source_index_content": None,
        "project_review_content": None,
        "final_output_dir": None,
        "final_output_dir_web_crawl": None,
        "relationship_flowchart_markup": None,
        "class_diagram_markup": None,
        "package_diagram_markup": None,
        "sequence_diagrams_markup": [],
    }
    logger_main_prep = logging.getLogger(__name__)
    log_msg_parts = [
        f"Initial context prepared. local_dir_display_root: '{local_dir_display_root}', "
        f"final_project_name for context: '{final_project_name}'"
    ]
    if initial_context["crawl_url"]:
        log_msg_parts.append(f"crawl_url: {initial_context['crawl_url']}")
    if initial_context["crawl_sitemap"]:
        log_msg_parts.append(f"crawl_sitemap: {initial_context['crawl_sitemap']}")
    if initial_context["crawl_file"]:
        log_msg_parts.append(f"crawl_file: {initial_context['crawl_file']}")
    logger_main_prep.debug(", ".join(log_msg_parts))
    return initial_context


def _initialize_app(args: argparse.Namespace) -> ConfigDict:
    """Load application configuration and set up logging.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.

    Returns:
        ConfigDict: The loaded application configuration.

    Raises:
        SystemExit: If critical errors occur during initialization.
    """
    logger_init = logging.getLogger(__name__)
    config_data: ConfigDict = {}
    validation_exceptions: tuple[type[Exception], ...] = (ConfigError,)
    if JSONSCHEMA_AVAILABLE and jsonschema and hasattr(jsonschema, "exceptions"):
        jsonschema_validation_error: Optional[type[Exception]] = getattr(jsonschema.exceptions, "ValidationError", None)
        if jsonschema_validation_error:
            validation_exceptions += (jsonschema_validation_error,)

    try:
        config_path_str: str = str(args.config)
        config_data = load_config(config_path_str)
        logging_cfg_val: Any = config_data.get("logging", {})
        logging_cfg: dict[str, Any] = logging_cfg_val if isinstance(logging_cfg_val, dict) else {}
        setup_logging(logging_cfg)
        logger_init.info("Config loaded successfully from %s", config_path_str)
        logger_init.debug("Effective LLM Config: %s", config_data.get("llm"))
        logger_init.debug("Effective Source Config: %s", config_data.get("source"))
        logger_init.debug("Effective Output Config: %s", config_data.get("output"))
        return config_data
    except FileNotFoundError as e:
        logging.critical("Configuration file not found: %s", e)
        print(f"\n❌ ERROR: Configuration file not found: {e!s}", file=sys.stderr)
        sys.exit(1)
    except validation_exceptions as e_val:
        logging.critical("Config loading/validation failed: %s", e_val, exc_info=True)
        print(f"\n❌ ERROR: Config loading/validation failed: {e_val!s}", file=sys.stderr)
        sys.exit(1)
    except ImportError as e_imp:
        logging.critical("Missing required library for config: %s", e_imp)
        print(f"\n❌ ERROR: Missing library for config: {e_imp!s}. Install dependencies.", file=sys.stderr)
        sys.exit(1)
    except OSError as e_os:
        logging.critical("File system error during config loading: %s", e_os, exc_info=True)
        print(f"\n❌ ERROR: File system error: {e_os!s}", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, ValueError, KeyError, TypeError) as e_prog:
        logging.critical("Unexpected error during config processing: %s", e_prog, exc_info=True)
        print(f"\n❌ ERROR: Unexpected error: {e_prog!s}", file=sys.stderr)
        sys.exit(1)


def _log_run_flow_startup_info(initial_context: SharedContextDict) -> bool:
    """Log startup information for the flow and return if it's a web crawl.

    Args:
        initial_context (SharedContextDict): The prepared initial context.

    Returns:
        bool: True if the operation is determined to be a web crawl, False otherwise.
    """
    logger_run_flow = logging.getLogger(__name__)
    is_web_crawl_mode = False

    if initial_context.get("crawl_url"):
        source_description = str(initial_context["crawl_url"])
        logger_run_flow.info("Starting web content fetching for URL: %s", source_description)
        is_web_crawl_mode = True
    elif initial_context.get("crawl_sitemap"):
        source_description = str(initial_context["crawl_sitemap"])
        logger_run_flow.info("Starting web content fetching for sitemap: %s", source_description)
        is_web_crawl_mode = True
    elif initial_context.get("crawl_file"):
        source_description = str(initial_context["crawl_file"])
        logger_run_flow.info("Starting web content fetching for file: %s", source_description)
        is_web_crawl_mode = True
    elif initial_context.get("repo_url") or initial_context.get("local_dir"):
        source_desc_any: Any = initial_context.get("repo_url") or initial_context.get("local_dir")
        source_description = str(source_desc_any) if source_desc_any else "Code repository/directory"
        logger_run_flow.info("Starting tutorial generation for: %s", source_description)
        logger_run_flow.info("Output Language: %s", initial_context.get("language"))
        source_config_val: dict[str, Any] = initial_context.get("source_config", {})
        logger_run_flow.info("Active Source Profile: %s", source_config_val.get("language"))

    logger_run_flow.info("Output Directory Base: %s", initial_context.get("output_dir"))
    llm_cfg_for_log: dict[str, Any] = initial_context.get("llm_config", {})
    logger_run_flow.info(
        "Active LLM Provider: %s (%s)",
        llm_cfg_for_log.get("provider"),
        "local" if llm_cfg_for_log.get("is_local_llm") else "cloud",
    )
    logger_run_flow.info("Active LLM Model: %s", llm_cfg_for_log.get("model"))
    return is_web_crawl_mode


def _handle_flow_completion(initial_context: SharedContextDict, *, is_web_crawl_mode: bool) -> None:
    """Handle logging and printing messages after flow completion.

    Args:
        initial_context (SharedContextDict): The shared context after flow execution.
        is_web_crawl_mode (bool): True if the web crawling mode was active.

    Raises:
        SystemExit: If no valid output path is confirmed after flow completion.
    """
    logger_run_flow = logging.getLogger(__name__)
    final_dir_any: Any = initial_context.get("final_output_dir")

    if final_dir_any and isinstance(final_dir_any, str):
        final_dir_path = Path(final_dir_any)
        if final_dir_path.exists() and final_dir_path.is_dir():
            logger_run_flow.info("Processing completed successfully. Output in: %s", final_dir_path.resolve())
            print(f"\n✅ Processing complete! Files are in: {final_dir_path.resolve()}")
            return

    if is_web_crawl_mode:
        web_crawl_output_dir_any: Any = initial_context.get("final_output_dir_web_crawl")
        if web_crawl_output_dir_any and isinstance(web_crawl_output_dir_any, str):
            web_crawl_dir_path = Path(web_crawl_output_dir_any)
            if web_crawl_dir_path.exists() and web_crawl_dir_path.is_dir():
                log_msg = "Web crawling primarily completed. Raw files expected in: %s"
                logger_run_flow.info(log_msg, web_crawl_dir_path.resolve())
                print_msg = (
                    f"\n✅ Web crawling completed. Raw crawled files are expected in: {web_crawl_dir_path.resolve()}"
                )
                print(print_msg)
            else:
                log_msg_l1 = "Web crawling mode finished, but designated web output directory "
                log_msg_l2 = f"'{web_crawl_dir_path.resolve()}' does not exist. "
                log_msg_l3 = "Files might not have been saved by FetchWebPage node."
                logger_run_flow.warning(log_msg_l1 + log_msg_l2 + log_msg_l3)
                print(f"\n⚠️ Web crawling finished, but output directory {web_crawl_dir_path.resolve()} not found.")
            return

    log_msg_fail = "Flow finished, but a valid final output directory was not confirmed in shared context."
    if is_web_crawl_mode:
        log_msg_fail += " (Web crawl mode)"
    else:
        log_msg_fail += " (Code analysis mode)"
    logger_run_flow.error(log_msg_fail)
    print_msg_fail = "\n⚠️ ERROR: Flow finished, but the final output directory was not confirmed."
    print(print_msg_fail, file=sys.stderr)
    sys.exit(1)


def _run_flow(initial_context: SharedContextDict) -> None:
    """Create and run the appropriate processing flow based on the initial context.

    Args:
        initial_context (SharedContextDict): The `SharedContextDict` for the flow.

    Raises:
        SystemExit: If flow execution encounters a critical, unrecoverable error.
    """
    is_web_crawl_mode = _log_run_flow_startup_info(initial_context)

    try:
        llm_config_param: dict[str, Any] = initial_context.get("llm_config", {})
        cache_config_param: dict[str, Any] = initial_context.get("cache_config", {})

        if TYPE_CHECKING:
            from sourcelens.core.flow_engine_sync import Flow as RuntimeSourceLensFlow
        else:
            from sourcelens.core.flow_engine_sync import Flow as RuntimeSourceLensFlow

        if RuntimeSourceLensFlow is None:
            raise RuntimeError("SourceLensFlow type could not be resolved at runtime.")

        processing_flow: "SourceLensFlow" = create_tutorial_flow(
            llm_config_param,
            cache_config_param,
            initial_context,
        )
        processing_flow.run_standalone(initial_context)
        _handle_flow_completion(initial_context, is_web_crawl_mode=is_web_crawl_mode)

    except ImportError as e_imp_flow:
        logging.critical("Failed to import module during flow execution: %s", e_imp_flow)
        print(f"\n❌ ERROR: Module import missing: {e_imp_flow!s}", file=sys.stderr)
        sys.exit(1)
    except (TypeError, RuntimeError, ConfigError, ValueError, KeyError, AttributeError) as e_flow:
        logging.exception("ERROR: Processing failed during flow execution: %s", e_flow)
        print(f"\n❌ ERROR: Processing failed: {e_flow!s}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Run the main command-line entry point for the SourceLens application."""
    args: argparse.Namespace = parse_arguments()
    config_data_main: ConfigDict = _initialize_app(args)
    initial_shared_context: SharedContextDict = _prepare_initial_context(args, config_data_main)
    _run_flow(initial_shared_context)


if __name__ == "__main__":
    main()

# End of src/sourcelens/main.py
