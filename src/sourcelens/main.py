# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Command-line interface entry point for the sourceLens application.

Handles argument parsing, configuration loading, logging setup,
initial state preparation, and orchestration of the tutorial generation flow
for both codebases and web content using a modular flow-based architecture
with subcommands 'code' and 'web'.
"""

import argparse
import contextlib
import importlib.resources
import json
import logging
import os
import sys
from datetime import datetime
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
from sourcelens.utils._exceptions import LlmApiError
from sourcelens.utils.helpers import (
    get_youtube_video_title_and_id,
    is_youtube_url,
    sanitize_filename,
)

if TYPE_CHECKING:  # pragma: no cover
    pass


SharedContextDict: TypeAlias = dict[str, Any]
ResolvedFlowConfigData: TypeAlias = ConfigDict

_DEFAULT_LOG_DIR_MAIN: Final[str] = "logs"
_DEFAULT_LOG_LEVEL_MAIN: Final[str] = "INFO"
_DEFAULT_LOG_FORMAT_MAIN: Final[str] = "%(asctime)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s"

_DEFAULT_YT_BASE_NAME_FALLBACK_MAIN: Final[str] = "youtube_video"
_DEFAULT_WEB_BASE_NAME_FALLBACK_MAIN: Final[str] = "web_content"
_DEFAULT_CODE_BASE_NAME_FALLBACK_MAIN: Final[str] = "code_project"

_MAX_BASE_NAME_LEN_MAIN: Final[int] = 50
_DEFAULT_MAIN_OUTPUT_DIR_MAIN: Final[str] = "output"
_DEFAULT_GENERATED_TEXT_LANGUAGE_MAIN: Final[str] = "english"

logger_main: logging.Logger = logging.getLogger(__name__)

NoFilesFetchedError: Optional[type[Exception]] = None
try:
    n01_fetch_code_module_path_val: str = "FL01_code_analysis.nodes.n01_fetch_code"
    n01_fetch_code_module_obj = importlib.import_module(n01_fetch_code_module_path_val)
    NoFilesFetchedError = getattr(n01_fetch_code_module_obj, "NoFilesFetchedError", None)
    if NoFilesFetchedError is None:  # pragma: no cover

        class _PlaceholderNoFilesFetchedErrorNFSub(Exception):  # pylint: disable=C0115
            pass

        NoFilesFetchedError = _PlaceholderNoFilesFetchedErrorNFSub
except ImportError:  # pragma: no cover

    class _MissingModuleForNoFilesFetchedErrorNFSub(Exception):  # pylint: disable=C0115
        pass

    NoFilesFetchedError = _MissingModuleForNoFilesFetchedErrorNFSub
    logger_main.warning(
        "Could not dynamically import NoFilesFetchedError from FL01_code_analysis.nodes.n01_fetch_code. "
        "Using a placeholder. This might affect specific error handling for no files fetched in code analysis."
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


def _get_local_dir_display_root(local_dir: Optional[str]) -> str:
    """Return the display root for local directories, normalizing the path.

    Used for providing a consistent base path display in logs or context.

    Args:
        local_dir: The path string to the local directory. Can be relative or absolute.

    Returns:
        A normalized string representation of the local directory root (e.g., "./" or "my_project/").
        Returns an empty string if `local_dir` is None or empty.
    """
    if not local_dir or not isinstance(local_dir, str):
        return ""
    display_root_str_val: str = ""
    with contextlib.suppress(ValueError, TypeError, OSError):
        path_obj_val: Path = Path(local_dir)
        if path_obj_val:
            display_root_str_val = path_obj_val.as_posix()
            if display_root_str_val == ".":
                display_root_str_val = "./"
            elif display_root_str_val and not display_root_str_val.endswith("/"):  # pragma: no cover
                display_root_str_val += "/"
    return display_root_str_val


def setup_logging(log_config: dict[str, Any]) -> None:
    """Configure application-wide logging based on the provided configuration.

    Sets up logging handlers for console (stdout) and optionally for a file.
    The logging level and format are determined by `log_config`.

    Args:
        log_config: A dictionary containing logging configuration parameters.
                    Expected keys:
                    - 'log_dir' (str): Directory for log files.
                    - 'log_level' (str): Logging level (e.g., "INFO", "DEBUG").
                    - 'log_file' (Optional[str]): Path to a specific log file for this run.
                      If "NONE", file logging is disabled. If None and `log_dir` is set,
                      a default "sourcelens.log" is created in `log_dir`.
    """
    log_dir_str_val: str = str(log_config.get("log_dir", _DEFAULT_LOG_DIR_MAIN))
    log_level_str_val_upper: str = str(log_config.get("log_level", _DEFAULT_LOG_LEVEL_MAIN)).upper()
    log_level_int_val: int = getattr(logging, log_level_str_val_upper, logging.INFO)
    log_file_path_cfg_val: Optional[str] = log_config.get("log_file")
    log_file_to_use_path_val: Optional[Path] = None
    log_handlers_list: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file_path_cfg_val and log_file_path_cfg_val.upper() != "NONE":
        log_file_to_use_path_val = Path(log_file_path_cfg_val)
    elif not log_file_path_cfg_val:
        log_dir_path_obj_item: Path = Path(log_dir_str_val)
        log_file_to_use_path_val = log_dir_path_obj_item / "sourcelens.log"

    if log_file_to_use_path_val:
        try:
            log_file_to_use_path_val.parent.mkdir(parents=True, exist_ok=True)
            file_handler_obj = logging.FileHandler(log_file_to_use_path_val, encoding="utf-8", mode="a")
            log_handlers_list.append(file_handler_obj)
            logger_main.info("File logging enabled at: %s", log_file_to_use_path_val.resolve())
        except OSError as e_os_log_err_val:  # pragma: no cover
            print(
                f"ERROR: Failed to create log file at '{log_file_to_use_path_val}': {e_os_log_err_val}", file=sys.stderr
            )
            logger_main.error("File logging disabled due to setup error. Using console only.")
    else:
        logger_main.info("File logging is disabled.")

    logging.basicConfig(
        level=log_level_int_val, format=_DEFAULT_LOG_FORMAT_MAIN, handlers=log_handlers_list, force=True
    )
    logger_main.info("Logging initialized with level %s.", log_level_str_val_upper)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the SourceLens tool using subparsers.

    Defines arguments for global configuration, output naming, logging, LLM overrides,
    and flow-specific subcommands ("code" and "web") with their respective source options.

    Returns:
        An object containing all parsed command-line arguments.
        Each argument is accessible as an attribute of this object
        (e.g., `args.config`, `args.flow_command`, `args.repo`).
    """
    parser_obj = argparse.ArgumentParser(
        description="SourceLens: Generate tutorials from codebases or web content using AI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_obj.add_argument(
        "--config", default="config.json", metavar="FILE_PATH", help="Path to global config JSON file."
    )
    parser_obj.add_argument(
        "-n", "--name", metavar="OUTPUT_NAME", help="Override default output name for the tutorial/summary."
    )
    parser_obj.add_argument(
        "-o",
        "--output",
        metavar="MAIN_OUTPUT_DIR",
        type=Path,
        help="Override main output directory for generated files.",
    )
    parser_obj.add_argument(
        "--language", metavar="LANG", help="Override generated text language (e.g., 'english', 'slovak')."
    )
    parser_obj.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override logging level from config.",
    )
    parser_obj.add_argument(
        "--log-file",
        metavar="PATH_OR_NONE",
        help="Path to log file. Use 'NONE' to disable file logging if enabled by config.",
    )

    llm_overrides_group_obj = parser_obj.add_argument_group("LLM Overrides (common to all flows)")
    llm_overrides_group_obj.add_argument(
        "--llm-provider", metavar="ID", help="Override active LLM provider ID from config."
    )
    llm_overrides_group_obj.add_argument("--llm-model", metavar="NAME", help="Override LLM model name.")
    llm_overrides_group_obj.add_argument("--api-key", metavar="KEY", help="Override LLM API key directly.")
    llm_overrides_group_obj.add_argument("--base-url", metavar="URL", help="Override LLM API base URL.")

    subparsers_obj = parser_obj.add_subparsers(
        dest="flow_command", required=True, help="The type of analysis to perform."
    )

    code_parser_obj = subparsers_obj.add_parser(
        "code",
        aliases=["code_analysis"],
        help="Analyze source code from a repository or local directory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    code_source_group_obj = code_parser_obj.add_mutually_exclusive_group(required=True)
    code_source_group_obj.add_argument(
        "--dir", metavar="LOCAL_DIR", type=Path, help="Path to local codebase directory."
    )
    code_source_group_obj.add_argument("--repo", metavar="REPO_URL", help="URL of the GitHub repository.")
    code_parser_obj.add_argument(
        "-i", "--include", nargs="+", metavar="PATTERN", help="Override include file patterns."
    )
    code_parser_obj.add_argument(
        "-e", "--exclude", nargs="+", metavar="PATTERN", help="Override exclude file patterns."
    )
    code_parser_obj.add_argument("-s", "--max-size", type=int, metavar="BYTES", help="Override max file size (bytes).")
    code_parser_obj.set_defaults(internal_flow_name="FL01_code_analysis")

    web_parser_obj = subparsers_obj.add_parser(
        "web",
        aliases=["web_crawling"],
        help="Crawl and analyze content from web URLs, sitemaps, or files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    web_source_group_obj = web_parser_obj.add_mutually_exclusive_group(required=True)
    web_source_group_obj.add_argument("--crawl-url", metavar="WEB_URL", help="Root URL of a website to crawl.")
    web_source_group_obj.add_argument("--crawl-sitemap", metavar="SITEMAP_URL", help="URL of a sitemap.xml to crawl.")
    web_source_group_obj.add_argument(
        "--crawl-file", metavar="FILE_URL_OR_PATH", help="URL or local path to a single text/markdown file."
    )
    web_parser_obj.add_argument("--crawl-depth", type=int, metavar="N", help="Override max crawl recursion depth.")
    web_parser_obj.add_argument(
        "--processing-mode",
        choices=["minimalistic", "llm_extended"],
        default=None,
        help="Override web content processing mode (minimalistic or llm_extended).",
    )
    web_parser_obj.set_defaults(internal_flow_name="FL02_web_crawling")

    return parser_obj.parse_args()


def _get_internal_flow_name(cli_flow_command: str) -> str:
    """Map CLI flow command (e.g., "code") to internal flow package name.

    Args:
        cli_flow_command: The flow command string provided by the user via CLI.

    Returns:
        The corresponding internal flow name (e.g., "FL01_code_analysis").

    Raises:
        ValueError: If the `cli_flow_command` is not a recognized command.
    """
    internal_name_val: Optional[str] = CLI_COMMAND_TO_INTERNAL_FLOW_MAP.get(cli_flow_command)
    if internal_name_val is None:  # Should not happen with argparse choices
        raise ValueError(f"Unknown CLI flow command: {cli_flow_command}")  # pragma: no cover
    return internal_name_val


def _initialize_app_config_and_logging(args: argparse.Namespace) -> tuple[ResolvedFlowConfigData, str]:
    """Initialize configuration loader, resolve flow-specific config, and set up logging.

    This function handles the core setup for application configuration and logging
    before any flow execution begins. It determines which flow is being run and loads
    the appropriate default configuration, merging it with global settings and
    any overrides specified via command-line arguments.

    Args:
        args: Parsed command-line arguments from `parse_arguments()`.
              The `args.internal_flow_name` attribute must be set by the subparser.

    Returns:
        A tuple containing:
            - `resolved_flow_config`: The fully resolved
              configuration dictionary for the specified flow.
            - `internal_flow_name`: The internal name of the flow being executed
              (e.g., "FL01_code_analysis").

    Raises:
        SystemExit: If critical errors occur during configuration loading or logging setup,
                    such as missing default configuration files or unrecoverable parsing errors.
    """
    try:
        config_loader_instance_obj = ConfigLoader(str(args.config))
        internal_flow_name_str_val: str = args.internal_flow_name

        # --- MODIFICATION START ---
        # Use importlib.resources to find the path to the config file within the package
        flow_default_config_filename_str_val: str = "config.default.json"
        try:
            # This context manager finds the resource and provides a valid Path object
            # that works whether the code is run from source or an installed package.
            with importlib.resources.path(internal_flow_name_str_val, flow_default_config_filename_str_val) as p:
                flow_default_path_obj_val: Path = p
        except FileNotFoundError as e:
            err_msg_str_val: str = (
                f"Default config for flow '{internal_flow_name_str_val}' not found within the package. "
                f"Searched for '{flow_default_config_filename_str_val}' in package '{internal_flow_name_str_val}'."
            )
            print(f"CRITICAL ERROR: {err_msg_str_val}", file=sys.stderr)
            raise ConfigError(err_msg_str_val) from e
        # --- MODIFICATION END ---

        if not flow_default_path_obj_val.is_file():  # pragma: no cover
            err_msg_str_val = (
                f"Default config for flow '{internal_flow_name_str_val}' "
                f"not found at resolved path: {flow_default_path_obj_val}"
            )
            print(f"CRITICAL ERROR: {err_msg_str_val}", file=sys.stderr)
            raise ConfigError(err_msg_str_val)

        resolved_flow_config_dict_val: ResolvedFlowConfigData = config_loader_instance_obj.get_resolved_flow_config(
            flow_name=internal_flow_name_str_val,
            flow_default_config_path=flow_default_path_obj_val,
            cli_args=args,
        )

        common_config_dict_final_item: dict[str, Any] = resolved_flow_config_dict_val.get("common", {})
        logging_settings_dict_final_item: dict[str, Any] = common_config_dict_final_item.get("logging", {})
        if hasattr(args, "log_file") and args.log_file is not None:
            log_file_cli_val_any_item: Any = args.log_file
            logging_settings_dict_final_item["log_file"] = (
                str(log_file_cli_val_any_item) if log_file_cli_val_any_item else None
            )

        setup_logging(logging_settings_dict_final_item)
        logger_main.info("Global and flow-specific configuration loaded for flow: %s", internal_flow_name_str_val)
        return resolved_flow_config_dict_val, internal_flow_name_str_val

    except ConfigError as e_config_err_init_val:  # pragma: no cover
        print(f"ERROR: Configuration setup failed: {e_config_err_init_val!s}", file=sys.stderr)
        if not logger_main.handlers:
            logging.basicConfig(level=logging.ERROR, format=_DEFAULT_LOG_FORMAT_MAIN, stream=sys.stderr)
        logger_main.critical("Configuration error: %s", e_config_err_init_val, exc_info=True)
        sys.exit(1)
    except (FileNotFoundError, ValueError) as e_file_val_err_init_val:  # pragma: no cover
        print(f"ERROR: File or value error during config setup: {e_file_val_err_init_val!s}", file=sys.stderr)
        if not logger_main.handlers:
            logging.basicConfig(level=logging.ERROR, format=_DEFAULT_LOG_FORMAT_MAIN, stream=sys.stderr)
        logger_main.critical("File/Value error during config: %s", e_file_val_err_init_val, exc_info=True)
        sys.exit(1)
    except (ImportError, AttributeError, RuntimeError, OSError) as e_unexpected_init_err_val:  # pragma: no cover
        print(f"ERROR: Unexpected error during app initialization: {e_unexpected_init_err_val!s}", file=sys.stderr)
        if not logger_main.handlers:
            logging.basicConfig(level=logging.ERROR, format=_DEFAULT_LOG_FORMAT_MAIN, stream=sys.stderr)
        logger_main.critical("Unexpected initialization error: %s", e_unexpected_init_err_val, exc_info=True)
        sys.exit(1)


def _get_timestamp_prefix() -> str:
    """Generate a timestamp prefix in YYYYMMDD_HHMM format.

    Returns:
        The formatted timestamp string (e.g., "20250611_1910").
    """
    return datetime.now().strftime("%Y%m%d_%H%M")


def _derive_base_name_for_web_source(
    args: argparse.Namespace,
) -> tuple[str, str, Optional[str], Optional[str]]:
    """Derive a base name, type prefix, video ID, and title for web sources.

    Fetches YouTube title if applicable. Uses POSIX-style path separators.

    Args:
        args: Parsed command-line arguments from `argparse.ArgumentParser`.
              Expected to have one of `crawl_url`, `crawl_sitemap`, or `crawl_file`.

    Returns:
        A tuple (base_name, type_prefix, video_id, video_title).
        `base_name` is sanitized. `type_prefix` is "_yt_" or "_web_".
        `video_id` and `video_title` are non-None for YouTube URLs.
    """
    source_url_str_val_item: Optional[str] = None
    video_id_val_opt_item_val: Optional[str] = None
    video_title_val_opt_item_val: Optional[str] = None
    type_prefix_str_val_item: str = "_web_"
    base_name_str_val_item: str = _DEFAULT_WEB_BASE_NAME_FALLBACK_MAIN

    if args.crawl_url:
        source_url_str_val_item = str(args.crawl_url)
    elif args.crawl_sitemap:
        source_url_str_val_item = str(args.crawl_sitemap)  # pragma: no cover
    elif args.crawl_file:
        source_url_str_val_item = str(args.crawl_file)
    else:  # pragma: no cover
        return (
            base_name_str_val_item,
            type_prefix_str_val_item,
            video_id_val_opt_item_val,
            video_title_val_opt_item_val,
        )

    if source_url_str_val_item:
        if is_youtube_url(source_url_str_val_item):
            fetched_id_val_item, fetched_title_val_item = get_youtube_video_title_and_id(source_url_str_val_item)
            if fetched_id_val_item:
                video_id_val_opt_item_val, video_title_val_opt_item_val = fetched_id_val_item, fetched_title_val_item
                type_prefix_str_val_item = "_yt_"
                base_name_str_val_item = sanitize_filename(
                    video_title_val_opt_item_val or _DEFAULT_YT_BASE_NAME_FALLBACK_MAIN, max_len=_MAX_BASE_NAME_LEN_MAIN
                )
        if type_prefix_str_val_item == "_web_":
            parsed_url_obj_val_item = urlparse(source_url_str_val_item)
            if parsed_url_obj_val_item.scheme and parsed_url_obj_val_item.netloc:
                base_name_str_val_item = sanitize_filename(
                    parsed_url_obj_val_item.netloc
                    or Path(source_url_str_val_item).stem
                    or _DEFAULT_WEB_BASE_NAME_FALLBACK_MAIN,
                    max_len=_MAX_BASE_NAME_LEN_MAIN,
                )
            else:
                base_name_str_val_item = sanitize_filename(
                    Path(source_url_str_val_item).stem or _DEFAULT_WEB_BASE_NAME_FALLBACK_MAIN,
                    max_len=_MAX_BASE_NAME_LEN_MAIN,
                )
    final_base_name = base_name_str_val_item or _DEFAULT_WEB_BASE_NAME_FALLBACK_MAIN
    logger_main.debug(
        "_derive_base_name_for_web_source returning: base_name='%s', type_prefix='%s', id='%s', title='%s'",
        final_base_name,
        type_prefix_str_val_item,
        video_id_val_opt_item_val,
        video_title_val_opt_item_val,
    )
    return final_base_name, type_prefix_str_val_item, video_id_val_opt_item_val, video_title_val_opt_item_val


def _derive_base_name_for_code_source(args: argparse.Namespace) -> str:
    """Derive a base name for code analysis sources (repository URL or local directory).

    Prioritizes repository URL's last path component (without .git).
    If no repo URL, uses the name of the local directory.
    The derived name is sanitized for filesystem path compatibility.

    Args:
        args: Parsed command-line arguments from `argparse.ArgumentParser`.
              Expected to have `repo` (Optional[str]) and `dir` (Optional[Path]) attributes.

    Returns:
        A sanitized, derived base name suitable for use in output directory names.
        Returns a default name if derivation from source fails.
    """
    repo_url_val_any_item_val: Any = args.repo
    local_dir_val_any_item_val: Any = args.dir
    repo_url_str_opt_val_item: Optional[str] = (
        str(repo_url_val_any_item_val) if isinstance(repo_url_val_any_item_val, str) else None
    )
    local_dir_path_obj_opt_val_item: Optional[Path] = (
        local_dir_val_any_item_val if isinstance(local_dir_val_any_item_val, Path) else None
    )
    name_candidate_str_val_item: str = ""

    if repo_url_str_opt_val_item:
        with contextlib.suppress(ValueError, TypeError, AttributeError, OSError, IndexError):
            parsed_url_val_item = urlparse(repo_url_str_opt_val_item)
            if parsed_url_val_item.path:
                name_part_str_val_item = parsed_url_val_item.path.strip("/").split("/")[-1]
                name_candidate_str_val_item = name_part_str_val_item.removesuffix(".git")
    elif local_dir_path_obj_opt_val_item:
        with contextlib.suppress(OSError, ValueError, TypeError):
            name_candidate_str_val_item = local_dir_path_obj_opt_val_item.name

    sanitized_base_name_val = (
        sanitize_filename(name_candidate_str_val_item, max_len=_MAX_BASE_NAME_LEN_MAIN)
        or _DEFAULT_CODE_BASE_NAME_FALLBACK_MAIN
    )
    logger_main.debug(
        "_derive_base_name_for_code_source returning: '%s' (from candidate: '%s')",
        sanitized_base_name_val,
        name_candidate_str_val_item,
    )
    return sanitized_base_name_val


def _derive_project_name_from_source(
    args: argparse.Namespace, config_output_name: str, internal_flow_name: str
) -> tuple[str, Optional[str], Optional[str]]:
    """Derive the final project name for the run, including timestamp and type prefix.

    If a name is provided via CLI (`args.name`), it takes highest precedence.
    If `config_output_name` is not the auto-detect sentinel, it's used next.
    Otherwise, a name is derived from the source (URL or directory path),
    prefixed with a timestamp. The type prefix (e.g., "_code-", "_yt_", "_web_")
    is chosen based on `internal_flow_name` and source type.

    Args:
        args: Parsed command-line arguments.
        config_output_name: The `default_output_name` from the loaded configuration.
        internal_flow_name: The internal name of the flow being run (e.g., "FL01_code_analysis").

    Returns:
        A tuple: (final_project_name, video_id, video_title).
        `video_id` and `video_title` are relevant and non-None only for YouTube
        web crawling flows; otherwise, they are None.
    """
    logger_main.debug(
        "Deriving project name. CLI --name: '%s', Config default_output_name: '%s', Flow: '%s'",
        args.name,
        config_output_name,
        internal_flow_name,
    )
    if args.name:
        logger_main.debug("Using project name from CLI --name argument: '%s'", args.name)
        return str(args.name), None, None
    if config_output_name != AUTO_DETECT_OUTPUT_NAME:
        logger_main.debug(
            "Using project name from 'common.common_output_settings.default_output_name' in config: '%s'",
            config_output_name,
        )
        return config_output_name, None, None

    timestamp_prefix_str_val_item: str = _get_timestamp_prefix()
    logger_main.debug("Generated timestamp prefix for auto-name: '%s'", timestamp_prefix_str_val_item)

    base_name_str_item_val: str
    type_prefix_str_item_val: str
    video_id_val_opt_str_item: Optional[str] = None
    video_title_val_opt_str_item: Optional[str] = None

    if internal_flow_name == "FL01_code_analysis":
        base_name_str_item_val = _derive_base_name_for_code_source(args)
        type_prefix_str_item_val = "_code-"
    elif internal_flow_name == "FL02_web_crawling":
        base_name_str_item_val, type_prefix_str_item_val, video_id_val_opt_str_item, video_title_val_opt_str_item = (
            _derive_base_name_for_web_source(args)
        )
    else:  # pragma: no cover
        logger_main.warning(
            "Unknown internal_flow_name '%s' for project name derivation. Using generic fallback.", internal_flow_name
        )
        base_name_str_item_val = "unknown_project"
        type_prefix_str_item_val = "_flow_"

    final_project_name_str_val_item = (
        f"{timestamp_prefix_str_val_item}{type_prefix_str_item_val}{base_name_str_item_val}"
    )
    logger_main.debug(
        "Auto-derived project name: '%s' (components: timestamp='%s', type_prefix='%s', base_name='%s')",
        final_project_name_str_val_item,
        timestamp_prefix_str_val_item,
        type_prefix_str_item_val,
        base_name_str_item_val,
    )
    return final_project_name_str_val_item, video_id_val_opt_str_item, video_title_val_opt_str_item


def _prepare_common_initial_context(
    args: argparse.Namespace,
    resolved_flow_config: ResolvedFlowConfigData,
    internal_flow_name: str,
    final_project_name: str,
) -> SharedContextDict:
    """Prepare the common part of the initial_context for any flow.

    This initializes shared context entries like resolved configurations,
    project name, output directory, language, and placeholders for flow outputs.

    Args:
        args: Parsed command-line arguments.
        resolved_flow_config: The fully resolved configuration for the current flow.
        internal_flow_name: The internal name of the flow being executed.
        final_project_name: The derived project name for this specific run.

    Returns:
        The base `SharedContextDict` populated with common parameters.
    """
    common_settings_dict_val_item: dict[str, Any] = resolved_flow_config.get("common", {})
    common_output_settings_dict_item_val: dict[str, Any] = common_settings_dict_val_item.get(
        "common_output_settings", {}
    )
    flow_specific_config_dict_item_val: dict[str, Any] = resolved_flow_config.get(internal_flow_name, {})

    main_out_dir_cfg_str_val_item: str = str(
        common_output_settings_dict_item_val.get("main_output_directory", _DEFAULT_MAIN_OUTPUT_DIR_MAIN)
    )
    final_main_out_dir_str_val_item: str = str(args.output) if args.output else main_out_dir_cfg_str_val_item

    gen_text_lang_cfg_str_val_item: str = str(
        common_output_settings_dict_item_val.get("generated_text_language", _DEFAULT_GENERATED_TEXT_LANGUAGE_MAIN)
    )
    final_gen_text_lang_str_val_item: str = str(args.language) if args.language else gen_text_lang_cfg_str_val_item

    initial_context_dict_val_obj: SharedContextDict = {
        "config": resolved_flow_config,
        "llm_config": resolved_flow_config.get("resolved_llm_config", {}),
        "cache_config": common_settings_dict_val_item.get("cache_settings", {}),
        "project_name": final_project_name,
        "output_dir": final_main_out_dir_str_val_item,
        "language": final_gen_text_lang_str_val_item,
        "current_operation_mode": internal_flow_name,
        "current_mode_output_options": flow_specific_config_dict_item_val.get("output_options", {}),
    }
    logger_main.debug(
        "_prepare_common_initial_context resulted in 'project_name': '%s'", initial_context_dict_val_obj["project_name"]
    )

    placeholder_keys_dict_val_item: dict[str, Any] = {
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
    for key_ph_str_val, default_val_ph_item_obj in placeholder_keys_dict_val_item.items():
        initial_context_dict_val_obj.setdefault(key_ph_str_val, default_val_ph_item_obj)
    return initial_context_dict_val_obj


def _add_code_analysis_context_overrides(
    initial_context: SharedContextDict, args: argparse.Namespace, resolved_flow_config: ResolvedFlowConfigData
) -> None:
    """Add specific context items for FL01_code_analysis flow to the initial context.

    Args:
        initial_context: The initial context dictionary to update.
        args: Parsed command-line arguments relevant to code analysis.
        resolved_flow_config: The fully resolved configuration for the code analysis flow.
    """
    flow_specific_cfg_block_val_obj: dict[str, Any] = resolved_flow_config.get("FL01_code_analysis", {})
    source_options_cfg_val_obj: dict[str, Any] = flow_specific_cfg_block_val_obj.get("source_options", {})

    initial_context.update(
        {
            "repo_url": args.repo,
            "local_dir": str(args.dir) if args.dir else None,
            "local_dir_display_root": _get_local_dir_display_root(str(args.dir) if args.dir else None),
            "source_config": flow_specific_cfg_block_val_obj.get("source_config", {}),
            "github_token": flow_specific_cfg_block_val_obj.get("resolved_github_token"),
            "include_patterns": set(source_options_cfg_val_obj.get("include_patterns", [])),
            "exclude_patterns": set(source_options_cfg_val_obj.get("default_exclude_patterns", [])),
            "max_file_size": source_options_cfg_val_obj.get("max_file_size_bytes"),
            "use_relative_paths": bool(source_options_cfg_val_obj.get("use_relative_paths", True)),
        }
    )


def _add_web_crawling_context_overrides(
    initial_context: SharedContextDict,
    args: argparse.Namespace,
    resolved_flow_config: ResolvedFlowConfigData,
    yt_video_id: Optional[str],
    yt_video_title: Optional[str],
) -> None:
    """Add specific context items for FL02_web_crawling flow to the initial context.

    Args:
        initial_context: The initial context dictionary to update.
        args: Parsed command-line arguments relevant to web crawling.
        resolved_flow_config: The fully resolved configuration for the web crawling flow.
        yt_video_id: Extracted YouTube video ID, if the source URL was a YouTube video.
        yt_video_title: Extracted YouTube video title, if applicable.
    """
    flow_specific_cfg_block_web_val_obj: dict[str, Any] = resolved_flow_config.get("FL02_web_crawling", {})
    crawler_options_cfg_val_obj: dict[str, Any] = flow_specific_cfg_block_web_val_obj.get("crawler_options", {})
    crawl_file_final_path_str_obj: Optional[str] = None

    if args.crawl_file:
        crawl_file_str_item_obj: str = str(args.crawl_file)
        if not is_youtube_url(crawl_file_str_item_obj):
            try:
                path_obj_crawl_file_item_obj = Path(crawl_file_str_item_obj)
                is_likely_local_path_bool_obj = os.sep in crawl_file_str_item_obj or (
                    os.path.altsep and os.path.altsep in crawl_file_str_item_obj
                )
                if not urlparse(crawl_file_str_item_obj).scheme and (
                    path_obj_crawl_file_item_obj.is_file()
                    or (is_likely_local_path_bool_obj and not path_obj_crawl_file_item_obj.exists())
                ):  # pragma: no cover
                    crawl_file_final_path_str_obj = str(path_obj_crawl_file_item_obj.resolve())
                else:  # pragma: no cover
                    crawl_file_final_path_str_obj = crawl_file_str_item_obj
            except (OSError, ValueError, TypeError) as e_path_resolve_err_obj:  # pragma: no cover
                logger_main.warning(
                    "Could not resolve --crawl-file '%s' as local path: %s. Treating as string.",
                    crawl_file_str_item_obj,
                    e_path_resolve_err_obj,
                )
                crawl_file_final_path_str_obj = crawl_file_str_item_obj
        else:
            crawl_file_final_path_str_obj = crawl_file_str_item_obj

    initial_context.update(
        {
            "crawl_url": args.crawl_url,
            "crawl_sitemap": args.crawl_sitemap,
            "crawl_file": crawl_file_final_path_str_obj,
            "cli_crawl_depth": crawler_options_cfg_val_obj.get("max_depth_recursive"),
            "processing_mode": crawler_options_cfg_val_obj.get("processing_mode"),
            "current_youtube_video_id": yt_video_id,
            "current_youtube_video_title": yt_video_title,
            "cli_extract_audio_enabled": getattr(args, "extract_audio", False)
            if hasattr(args, "extract_audio")
            else False,
        }
    )


def _prepare_runtime_initial_context(
    args: argparse.Namespace, resolved_flow_config: ResolvedFlowConfigData, internal_flow_name: str
) -> SharedContextDict:
    """Prepare the initial shared context for the specific flow to be run.

    This orchestrates the derivation of the project name and then populates
    the `initial_context` with common settings, followed by flow-specific settings.

    Args:
        args: Parsed command-line arguments from `argparse.ArgumentParser`.
        resolved_flow_config: The fully resolved configuration for the current flow.
        internal_flow_name: The internal name of the flow being executed
                            (e.g., "FL01_code_analysis").

    Returns:
        The fully prepared initial context dictionary for the pipeline.
    """
    logger_main.debug("Preparing initial_context for flow: '%s'. Args passed: %s", internal_flow_name, args)
    common_output_settings_dict_item_obj: dict[str, Any] = resolved_flow_config.get("common", {}).get(
        "common_output_settings", {}
    )
    output_name_from_config_str_obj: str = str(
        common_output_settings_dict_item_obj.get("default_output_name", AUTO_DETECT_OUTPUT_NAME)
    )
    logger_main.debug(
        "Output name from config (before CLI override check in _derive_project_name_from_source): '%s'",
        output_name_from_config_str_obj,
    )

    final_project_name_str_obj: str
    yt_video_id_val_opt_obj: Optional[str]
    yt_video_title_val_opt_obj: Optional[str]
    final_project_name_str_obj, yt_video_id_val_opt_obj, yt_video_title_val_opt_obj = _derive_project_name_from_source(
        args, output_name_from_config_str_obj, internal_flow_name
    )
    logger_main.debug(
        "Derived final_project_name: '%s', yt_video_id: '%s', yt_video_title: '%s'",
        final_project_name_str_obj,
        yt_video_id_val_opt_obj,
        yt_video_title_val_opt_obj,
    )

    initial_context_dict_val_obj_item: SharedContextDict = _prepare_common_initial_context(
        args, resolved_flow_config, internal_flow_name, final_project_name_str_obj
    )
    logger_main.debug(
        "Initial context after _prepare_common_initial_context, 'project_name': '%s'",
        initial_context_dict_val_obj_item["project_name"],
    )

    if internal_flow_name == "FL01_code_analysis":
        _add_code_analysis_context_overrides(initial_context_dict_val_obj_item, args, resolved_flow_config)
    elif internal_flow_name == "FL02_web_crawling":
        _add_web_crawling_context_overrides(
            initial_context_dict_val_obj_item,
            args,
            resolved_flow_config,
            yt_video_id_val_opt_obj,
            yt_video_title_val_opt_obj,
        )
    logger_main.debug(
        "Runtime initial_context for flow '%s'. Project name: '%s'",
        internal_flow_name,
        initial_context_dict_val_obj_item["project_name"],
    )
    if logger_main.isEnabledFor(logging.DEBUG):  # pragma: no cover
        try:
            log_context_copy_dict_obj: dict[str, Any] = json.loads(
                json.dumps(initial_context_dict_val_obj_item, default=str)
            )
            if (
                "llm_config" in log_context_copy_dict_obj
                and isinstance(log_context_copy_dict_obj["llm_config"], dict)
                and "api_key" in log_context_copy_dict_obj["llm_config"]
            ):
                log_context_copy_dict_obj["llm_config"]["api_key"] = "***REDACTED***"
            if "github_token" in log_context_copy_dict_obj:
                log_context_copy_dict_obj["github_token"] = "***REDACTED***"
            logger_main.debug("Full initial_context (redacted): %s", json.dumps(log_context_copy_dict_obj, indent=2))
        except (TypeError, ValueError) as e_json_dump_err_obj:
            logger_main.debug("Could not serialize initial_context for debug logging: %s", e_json_dump_err_obj)
    return initial_context_dict_val_obj_item


def _get_flow_creator_function(internal_flow_name: str) -> Callable[[SharedContextDict], SourceLensFlow]:
    """Dynamically import and retrieve the flow creation function for the specified flow.

    Uses `FLOW_MODULE_LOOKUP` to find the module path and function name.

    Args:
        internal_flow_name: The internal name of the flow (e.g., "FL01_code_analysis").

    Returns:
        The flow creation function.

    Raises:
        ValueError: If `internal_flow_name` is not supported.
        ImportError: If the flow module cannot be imported.
        AttributeError: If the creator function is not found in the module.
    """
    logger_main.debug("Attempting to get flow creator for internal flow: %s", internal_flow_name)
    if internal_flow_name not in FLOW_MODULE_LOOKUP:  # pragma: no cover
        supported_keys_str_val_obj: str = ", ".join(list(FLOW_MODULE_LOOKUP.keys()))
        raise ValueError(
            f"Internal flow '{internal_flow_name}' not supported. Supported: [{supported_keys_str_val_obj}]"
        )

    module_path_str_item_obj, creator_func_name_str_obj = FLOW_MODULE_LOOKUP[internal_flow_name]

    try:
        flow_module_obj_val_obj = importlib.import_module(module_path_str_item_obj)
        logger_main.info("Successfully imported module: %s", module_path_str_item_obj)
    except ImportError as e_import_module_err_obj:  # pragma: no cover
        logger_main.error("Failed to import module %s: %s", module_path_str_item_obj, e_import_module_err_obj)
        err_msg_import_val_obj: str = (
            f"Could not import module '{module_path_str_item_obj}' for internal flow '{internal_flow_name}'. "
            "Ensure flow package is correctly installed and accessible."
        )
        raise ImportError(err_msg_import_val_obj) from e_import_module_err_obj

    try:
        creator_function_val_obj: Callable[[SharedContextDict], SourceLensFlow] = cast(
            Callable[[SharedContextDict], SourceLensFlow], getattr(flow_module_obj_val_obj, creator_func_name_str_obj)
        )
        logger_main.info(
            "Successfully retrieved creator: %s from %s", creator_func_name_str_obj, module_path_str_item_obj
        )
        return creator_function_val_obj
    except AttributeError as e_attr_creator_err_obj:  # pragma: no cover
        logger_main.error(
            "Creator function %s not found in module %s: %s",
            creator_func_name_str_obj,
            module_path_str_item_obj,
            e_attr_creator_err_obj,
        )
        err_msg_attr_val_obj: str = (
            f"Creator function '{creator_func_name_str_obj}' not found in module '{module_path_str_item_obj}'."
        )
        raise AttributeError(err_msg_attr_val_obj) from e_attr_creator_err_obj


def _log_run_flow_startup_info(initial_context: SharedContextDict, internal_flow_name: str) -> None:
    """Log essential startup information before running the processing flow.

    This includes the source type, project name, output directory, language,
    and active LLM provider/model for the current flow execution.

    Args:
        initial_context: The prepared shared context for the flow.
        internal_flow_name: The internal name of the flow being run.
    """
    source_description_str_val_obj: str = "N/A"
    if internal_flow_name == "FL01_code_analysis":
        source_val_code_item_obj: Optional[Any] = initial_context.get("repo_url") or initial_context.get("local_dir")
        source_description_str_val_obj = (
            str(source_val_code_item_obj) if source_val_code_item_obj is not None else "N/A"
        )
        logger_main.info("Starting code analysis for: %s", source_description_str_val_obj)

        source_config_dict_item_obj: dict[str, Any] = cast(dict, initial_context.get("source_config", {}))
        lang_name_val_str_item_obj: str = str(source_config_dict_item_obj.get("language_name_for_llm", "N/A"))
        parser_type_val_str_item_obj: str = str(source_config_dict_item_obj.get("parser_type", "N/A"))
        logger_main.info(
            "Active Code Language Profile: %s (Parser: %s)", lang_name_val_str_item_obj, parser_type_val_str_item_obj
        )

    elif internal_flow_name == "FL02_web_crawling":
        source_val_web_item_obj: Optional[Any] = (
            initial_context.get("crawl_url")
            or initial_context.get("crawl_sitemap")
            or initial_context.get("crawl_file")
        )
        source_description_str_val_obj = str(source_val_web_item_obj) if source_val_web_item_obj is not None else "N/A"
        if initial_context.get("current_youtube_video_id"):
            yt_title_val_str_item_obj: str = str(initial_context.get("current_youtube_video_title", "N/A"))
            source_description_str_val_obj += f" (YouTube Title: {yt_title_val_str_item_obj})"
        logger_main.info("Starting web content analysis for: %s", source_description_str_val_obj)
    else:  # pragma: no cover
        logger_main.error("Unknown internal flow name '%s' for startup info logging.", internal_flow_name)

    logger_main.info("Output Project Name (used for dir): %s", initial_context.get("project_name"))
    logger_main.info("Main Output Directory Base: %s", initial_context.get("output_dir"))
    logger_main.info("Generated Text Language: %s", initial_context.get("language"))

    llm_config_for_log_val_obj: dict[str, Any] = cast(dict, initial_context.get("llm_config", {}))
    provider_name_str_val_obj: str = str(llm_config_for_log_val_obj.get("provider", "N/A"))
    is_local_llm_bool_val_obj: Any = llm_config_for_log_val_obj.get("is_local_llm")
    llm_type_str_val_obj: str = (
        "local" if isinstance(is_local_llm_bool_val_obj, bool) and is_local_llm_bool_val_obj else "cloud"
    )
    model_name_str_val_obj: str = str(llm_config_for_log_val_obj.get("model", "N/A"))
    log_msg_l1: str = (
        f"Active LLM Provider for flow '{internal_flow_name}': {provider_name_str_val_obj} ({llm_type_str_val_obj})"
    )
    log_msg_l2: str = f"Active LLM Model for flow '{internal_flow_name}': {model_name_str_val_obj}"
    logger_main.info(log_msg_l1)
    logger_main.info(log_msg_l2)


def _check_operation_mode_enabled(internal_flow_name: str, resolved_config: ResolvedFlowConfigData) -> None:
    """Verify if the determined flow is enabled in the configuration.

    Exits the application with an error if the flow is disabled.

    Args:
        internal_flow_name: The internal name of the flow (e.g., "FL01_code_analysis").
        resolved_config: The fully resolved configuration for this specific flow.
    """
    flow_specific_settings_dict_val_obj: dict[str, Any] = resolved_config.get(internal_flow_name, {})
    is_enabled_bool_val_obj: bool = bool(flow_specific_settings_dict_val_obj.get("enabled", False))

    if not is_enabled_bool_val_obj:  # pragma: no cover
        disabled_msg_str_val_obj: str = f"Flow '{internal_flow_name}' disabled in configuration. Halting."
        logger_main.error(disabled_msg_str_val_obj)
        print(f"\n❌ ERROR: {disabled_msg_str_val_obj}", file=sys.stderr)
        sys.exit(1)


def _validate_flow_output_or_exit(initial_context: SharedContextDict, internal_flow_name: str) -> None:
    """Validate if essential output was generated by the flow; exit if not.

    For web crawling in "minimalistic" mode, checks if the raw crawl output directory
    was set. For "llm_extended" mode, checks if any files were populated for LLM analysis.
    Currently, no specific output validation is implemented for "FL01_code_analysis" here.

    Args:
        initial_context: The shared context after the flow has run.
        internal_flow_name: The internal name of the flow that was run.
    """
    if internal_flow_name == "FL01_code_analysis":
        pass
    elif internal_flow_name == "FL02_web_crawling":
        web_files_populated_bool_obj: bool = bool(initial_context.get("files"))
        raw_crawl_output_dir_set_bool_obj: bool = bool(initial_context.get("final_output_dir_web_crawl"))

        resolved_flow_config_val_dict_obj: ResolvedFlowConfigData = cast(
            ResolvedFlowConfigData, initial_context.get("config", {})
        )
        web_flow_settings_val_dict_obj: dict[str, Any] = resolved_flow_config_val_dict_obj.get(internal_flow_name, {})
        crawler_options_config: dict[str, Any] = web_flow_settings_val_dict_obj.get("crawler_options", {})
        processing_mode_web_str_val_obj: str = str(crawler_options_config.get("processing_mode", "minimalistic"))

        essential_output_is_missing_bool_obj: bool = False
        if processing_mode_web_str_val_obj == "llm_extended" and not web_files_populated_bool_obj:  # pragma: no cover
            essential_output_is_missing_bool_obj = True
            logger_main.error("Halting: No web content for LLM analysis after fetch (llm_extended mode).")
        elif (
            processing_mode_web_str_val_obj == "minimalistic" and not raw_crawl_output_dir_set_bool_obj
        ):  # pragma: no cover
            if not initial_context.get("current_youtube_video_id") and not initial_context.get("final_output_dir"):
                essential_output_is_missing_bool_obj = True
                logger_main.error("Halting: Raw crawl output dir not set after fetch (minimalistic general web).")

        if essential_output_is_missing_bool_obj:  # pragma: no cover
            err_msg_l1_item: str = "\n❌ ERROR: No web content was successfully fetched or processed for selected mode."
            err_msg_l2_item: str = "       Please check target URL/sitemap, network, and config."
            print(err_msg_l1_item, file=sys.stderr)
            print(err_msg_l2_item, file=sys.stderr)
            sys.exit(1)


def _handle_flow_completion(initial_context: SharedContextDict, internal_flow_name: str) -> None:
    """Handle logging and printing messages after the main processing flow completes.

    Determines the type of output generated based on the flow and processing mode
    and prints a success message with the path to the main output directory.

    Args:
        initial_context: The shared context after flow execution.
        internal_flow_name: The internal name of the flow that was run.
    """
    final_output_path_str: Optional[str] = cast(Optional[str], initial_context.get("final_output_dir"))
    if not final_output_path_str and internal_flow_name == "FL02_web_crawling":
        final_output_path_str = cast(Optional[str], initial_context.get("final_output_dir_web_crawl"))

    final_output_path_obj_item: Path
    if not final_output_path_str:
        base_output_dir_path_obj_item: Path = Path(str(initial_context.get("output_dir")))
        project_name_dir_path_obj_item: Path = Path(str(initial_context.get("project_name")))
        final_output_path_obj_item = base_output_dir_path_obj_item / project_name_dir_path_obj_item
        # final_output_path_str = str(final_output_path_obj_item) # No longer needed as separate str
        logger_main.debug(
            "_handle_flow_completion: Using project_name from context: '%s' to form final_output_path: '%s'",
            initial_context.get("project_name"),
            str(final_output_path_obj_item),  # Log the string representation
        )
    else:
        final_output_path_obj_item = Path(final_output_path_str)
        log_msg_comp: str = (
            f"_handle_flow_completion: Using final_output_path directly from context: '{final_output_path_str}'"
        )
        logger_main.debug(log_msg_comp)

    output_type_message_str_obj: str = "Analysis"
    if internal_flow_name == "FL02_web_crawling":
        resolved_conf_val_dict_item_obj: Any = initial_context.get("config", {})
        resolved_conf_obj_item_obj: ResolvedFlowConfigData = cast(
            ResolvedFlowConfigData, resolved_conf_val_dict_item_obj
        )
        web_flow_opts_dict_item_obj: dict[str, Any] = resolved_conf_obj_item_obj.get(internal_flow_name, {})
        crawler_options_config: dict[str, Any] = web_flow_opts_dict_item_obj.get("crawler_options", {})
        processing_mode_val_str_item_obj: str = str(crawler_options_config.get("processing_mode", "minimalistic"))

        if initial_context.get("current_youtube_video_id"):
            output_type_message_str_obj = "YouTube content summary/transcript"
        elif processing_mode_val_str_item_obj == "minimalistic":
            output_type_message_str_obj = "Raw crawled web content (summary/tutorial generation skipped)"
        else:
            output_type_message_str_obj = "Web summary/tutorial"

    elif internal_flow_name == "FL01_code_analysis":
        output_type_message_str_obj = "Code tutorial"

    if final_output_path_obj_item.exists() and final_output_path_obj_item.is_dir():
        resolved_path_str_item_obj: str = str(final_output_path_obj_item.resolve())
        logger_main.info(
            "%s processing completed. Output in: %s",
            output_type_message_str_obj.capitalize(),
            resolved_path_str_item_obj,
        )
        print(
            f"\n✅ {output_type_message_str_obj.capitalize()} processing complete! "
            f"Files are in: {resolved_path_str_item_obj}"
        )
        return

    log_msg_failure_str_item: str = (
        "Flow finished, but final output directory was not found or is not a directory."  # pragma: no cover
    )
    print(
        f"\n⚠️ ERROR: {log_msg_failure_str_item} Path: {final_output_path_obj_item.resolve()}", file=sys.stderr
    )  # pragma: no cover
    logger_main.error(log_msg_failure_str_item + f" (Flow: {internal_flow_name})")  # pragma: no cover
    sys.exit(1)  # pragma: no cover


def _run_flow(initial_context: SharedContextDict, internal_flow_name: str) -> None:
    """Instantiate and execute the appropriate processing flow based on `internal_flow_name`.

    This function performs critical pre-run checks (e.g., if the flow is enabled),
    logs startup information, dynamically creates the flow instance, runs it,
    validates essential outputs, and handles final completion messages or errors.

    Args:
        initial_context: The prepared initial shared context for the flow.
        internal_flow_name: The internal name of the flow to run (e.g., "FL01_code_analysis").

    Raises:
        SystemExit: If the flow is disabled, fails to create, encounters a critical
                    execution error, or if essential outputs are missing post-execution.
    """
    _check_operation_mode_enabled(internal_flow_name, cast(ResolvedFlowConfigData, initial_context.get("config", {})))
    _log_run_flow_startup_info(initial_context, internal_flow_name)

    processing_flow_instance_obj_item_val: Optional[SourceLensFlow] = None
    try:
        create_flow_function_val_obj_item_val: Callable[[SharedContextDict], SourceLensFlow] = (
            _get_flow_creator_function(internal_flow_name)
        )
        processing_flow_instance_obj_item_val = create_flow_function_val_obj_item_val(initial_context)
        logger_main.info("Pipeline for flow '%s' created successfully.", internal_flow_name)
    except (ImportError, ValueError, AttributeError) as e_create_flow_err_val_item_val_item:  # pragma: no cover
        logger_main.critical(
            "Failed to create pipeline for %s: %s",
            internal_flow_name,
            e_create_flow_err_val_item_val_item,
            exc_info=True,
        )
        sys.exit(1)

    if not processing_flow_instance_obj_item_val:  # pragma: no cover
        logger_main.error("Pipeline for flow '%s' could not be instantiated. Halting.", internal_flow_name)
        sys.exit(1)

    try:
        logger_main.info("Running the %s pipeline...", internal_flow_name)
        processing_flow_instance_obj_item_val.run_standalone(initial_context)
        _validate_flow_output_or_exit(initial_context, internal_flow_name)
        _handle_flow_completion(initial_context, internal_flow_name)

    except (
        ConfigError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
        OSError,
        ImportError,
        LlmApiError,
    ) as e_flow_exec_val_item_val_item_val:
        if (
            internal_flow_name == "FL01_code_analysis"
            and NoFilesFetchedError is not None
            and isinstance(e_flow_exec_val_item_val_item_val, NoFilesFetchedError)
        ):  # pragma: no cover
            err_msg_no_files_item: str = "No files fetched for code analysis. This is a critical error."
            logger_main.error("%s: %s", err_msg_no_files_item, e_flow_exec_val_item_val_item_val, exc_info=False)
            print(
                f"\n❌ CRITICAL ERR : No source files found for analysis. Details: {e_flow_exec_val_item_val_item_val}",
                file=sys.stderr,
            )
            sys.exit(1)
        else:  # pragma: no cover
            logger_main.critical(
                "Error during %s pipeline execution: %s",
                internal_flow_name,
                e_flow_exec_val_item_val_item_val,
                exc_info=True,
            )
            print(f"\n❌ ERROR: Pipeline execution failed: {e_flow_exec_val_item_val_item_val!s}", file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:  # pragma: no cover
        logger_main.warning("Execution interrupted by user (KeyboardInterrupt).")
        print("\n❌ Execution interrupted by user.", file=sys.stderr)
        sys.exit(130)


def main() -> None:
    """Run the main command-line entry point for the SourceLens application.

    Parses arguments, initializes configuration and logging, prepares the
    initial shared context based on the chosen flow (code or web), and then
    runs the selected processing flow.
    """
    args_parsed_ns_val_obj_item: argparse.Namespace = parse_arguments()
    internal_flow_name_to_run_str_val_obj_item: str = args_parsed_ns_val_obj_item.internal_flow_name
    resolved_flow_configuration_val_dict_obj_item: ResolvedFlowConfigData
    resolved_flow_configuration_val_dict_obj_item, _ = _initialize_app_config_and_logging(args_parsed_ns_val_obj_item)

    initial_shared_context_val_dict_obj_item: SharedContextDict = _prepare_runtime_initial_context(
        args_parsed_ns_val_obj_item,
        resolved_flow_configuration_val_dict_obj_item,
        internal_flow_name_to_run_str_val_obj_item,
    )
    _run_flow(initial_shared_context_val_dict_obj_item, internal_flow_name_to_run_str_val_obj_item)


if __name__ == "__main__":  # pragma: no cover
    main()

# End of src/sourcelens/main.py
