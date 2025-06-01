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
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlparse

from typing_extensions import TypeAlias

from sourcelens.config import AUTO_DETECT_OUTPUT_NAME, ConfigError, load_config
from sourcelens.flow import create_tutorial_flow

# Import the new exception from FetchCode
from sourcelens.nodes.code.n01_fetch_code import NoFilesFetchedError
from sourcelens.utils.helpers import sanitize_filename

if TYPE_CHECKING:
    pass

SharedContextDict: TypeAlias = dict[str, Any]
ConfigData: TypeAlias = dict[str, Any]

DEFAULT_LOG_DIR_MAIN_FALLBACK: str = "logs"
DEFAULT_LOG_LEVEL_MAIN_FALLBACK: str = "INFO"
DEFAULT_LOG_FORMAT: str = "%(asctime)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s"

DEFAULT_WEB_OUTPUT_NAME_FALLBACK: str = "web-content-analysis"
DEFAULT_CODE_OUTPUT_NAME_FALLBACK: str = "code-analysis-output"
MAX_PROJECT_NAME_LEN_FROM_URL_MAIN: int = 40
DEFAULT_MAX_FILE_SIZE_FALLBACK: int = 150000


def _get_local_dir_display_root(local_dir: Optional[str]) -> str:
    """Return the display root for local directories, normalizing the path.

    This is used to create a user-friendly representation of the base path
    from which local files were scanned, especially when paths are relative.

    Args:
        local_dir: The path string to the local directory as provided by the user.
                   Can be None if no local directory is specified.

    Returns:
        A normalized string representation of the local directory root,
        typically ending with a forward slash (e.g., "my_project/").
        Returns an empty string if `local_dir` is None, empty, or invalid.
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
            elif not display_root_str.endswith("/"):
                display_root_str += "/"
    return display_root_str


def setup_logging(log_config: dict[str, Any]) -> None:
    """Configure application-wide logging based on the provided configuration.

    Sets up logging to both a file (e.g., `sourcelens.log` in the configured
    log directory) and to standard output. The logging level and format
    are determined by the `log_config` dictionary. If file logging setup
    fails, it falls back to logging only to standard output.

    Args:
        log_config: A dictionary containing logging configuration parameters.
    """
    log_dir_str: str = str(log_config.get("log_dir", DEFAULT_LOG_DIR_MAIN_FALLBACK))
    log_level_str: str = str(log_config.get("log_level", DEFAULT_LOG_LEVEL_MAIN_FALLBACK)).upper()
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
            force=True,  # type: ignore[call-overload]
        )
        logging.getLogger(__name__).info("Logging initialized. Log file: %s", log_file.resolve() if log_file else "N/A")
    except OSError as e:
        print(f"ERROR: Failed create log dir/file '{log_file or log_dir}': {e}", file=sys.stderr)
        logging.basicConfig(
            level=log_level,
            format=DEFAULT_LOG_FORMAT,
            handlers=[logging.StreamHandler(sys.stdout)],
            force=True,  # type: ignore[call-overload]
        )
        logging.getLogger(__name__).error("File logging disabled due to setup error. Logging to stdout only.")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the SourceLens tool.

    Returns:
        An object containing the parsed command-line arguments.
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
    parser.add_argument("-n", "--name", metavar="OUTPUT_NAME", help="Override default output name from config.")
    parser.add_argument("-o", "--output", metavar="MAIN_OUTPUT_DIR", help="Override main output directory from config.")
    code_group = parser.add_argument_group("Code Analysis Options (if --repo or --dir)")
    code_group.add_argument("-i", "--include", nargs="+", metavar="PATTERN", help="Override include patterns for code.")
    code_group.add_argument("-e", "--exclude", nargs="+", metavar="PATTERN", help="Override exclude patterns for code.")
    code_group.add_argument("-s", "--max-size", type=int, metavar="BYTES", help="Override max file size for code.")
    parser.add_argument("--language", metavar="LANG", help="Override generated text language from config.")
    crawl_group = parser.add_argument_group("Web Crawling Options (if --crawl-*)")
    crawl_group.add_argument("--crawl-depth", type=int, metavar="N", help="Max crawl recursion depth for web.")
    crawl_group.add_argument("--crawl-output-subdir", metavar="NAME", help="Subdir name for raw crawled web content.")
    return parser.parse_args()


def _get_output_name_from_cli_or_config(args: argparse.Namespace, common_output_settings: dict[str, Any]) -> str:
    """Determine the output name based on CLI arguments and configuration.

    Args:
        args: The `argparse.Namespace` object containing parsed command-line arguments.
        common_output_settings: A dictionary representing the 'common_output_settings'
                                section of the application configuration.

    Returns:
        The determined output name as a string.
    """
    output_name_override_val: Any = args.name
    output_name_override: Optional[str] = (
        str(output_name_override_val) if isinstance(output_name_override_val, str) else None
    )
    if output_name_override and output_name_override.strip():
        return output_name_override.strip()

    config_default_name_val: Any = common_output_settings.get("default_output_name")
    config_default_name_str: Optional[str] = (
        str(config_default_name_val) if isinstance(config_default_name_val, str) else None
    )

    if config_default_name_str and config_default_name_str.strip():
        return config_default_name_str
    return AUTO_DETECT_OUTPUT_NAME


def _derive_name_from_web_source(args: argparse.Namespace) -> str:
    """Derive an output name specifically for web sources.

    Args:
        args: The `argparse.Namespace` object containing parsed command-line arguments.

    Returns:
        A derived name for web analysis.
    """
    source_url_val: Any = args.crawl_url or args.crawl_sitemap or args.crawl_file
    source_url: Optional[str] = str(source_url_val) if isinstance(source_url_val, str) else None

    if source_url:
        with contextlib.suppress(ValueError, TypeError, AttributeError, OSError, IndexError):
            parsed_url = urlparse(source_url)
            name_candidate: str = parsed_url.netloc or Path(parsed_url.path).stem or ""
            if name_candidate:
                return sanitize_filename(name_candidate, max_len=MAX_PROJECT_NAME_LEN_FROM_URL_MAIN)
    return DEFAULT_WEB_OUTPUT_NAME_FALLBACK


def _derive_name_from_code_source(args: argparse.Namespace) -> str:
    """Derive an output name specifically for code sources.

    Args:
        args: The `argparse.Namespace` object containing parsed command-line arguments.

    Returns:
        A derived name for code analysis.
    """
    repo_url_val: Any = args.repo
    local_dir_val: Any = args.dir
    repo_url: Optional[str] = str(repo_url_val) if isinstance(repo_url_val, str) else None
    local_dir: Optional[str] = str(local_dir_val) if isinstance(local_dir_val, str) else None

    if repo_url:
        with contextlib.suppress(ValueError, TypeError, AttributeError, OSError, IndexError):
            parsed_url = urlparse(repo_url)
            if parsed_url.path:
                name_part = parsed_url.path.strip("/").split("/")[-1]
                derived_name_base = name_part.removesuffix(".git")
                if derived_name_base:
                    return derived_name_base
    elif local_dir:
        with contextlib.suppress(OSError, ValueError, TypeError):
            return Path(local_dir).resolve().name
    return DEFAULT_CODE_OUTPUT_NAME_FALLBACK


def _derive_name_from_source_if_auto(args: argparse.Namespace, current_output_name: str) -> str:
    """Derive the output name from the input source if it's set to auto-detect.

    Args:
        args: The `argparse.Namespace` object containing parsed command-line arguments.
        current_output_name: The output name determined so far.

    Returns:
        The final output name as a string.
    """
    if current_output_name != AUTO_DETECT_OUTPUT_NAME:
        return current_output_name

    operation_mode = _determine_operation_mode(args)
    derived_name: str
    if operation_mode == "web":
        derived_name = _derive_name_from_web_source(args)
    else:
        derived_name = _derive_name_from_code_source(args)

    if not derived_name:
        logging.getLogger(__name__).error("Name derivation failed unexpectedly, using generic fallback.")
        fallback = DEFAULT_CODE_OUTPUT_NAME_FALLBACK if operation_mode == "code" else DEFAULT_WEB_OUTPUT_NAME_FALLBACK
        derived_name = fallback
    return derived_name


def _get_path_patterns_for_code_analysis(
    args: argparse.Namespace, code_analysis_source_config: dict[str, Any]
) -> tuple[set[str], set[str]]:
    """Get effective include and exclude path patterns for code analysis.

    Args:
        args: The `argparse.Namespace` object with command-line arguments.
        code_analysis_source_config: The 'source_config' part of the resolved
                                     'code_analysis' configuration.

    Returns:
        A tuple containing two sets of strings: include patterns and exclude patterns.
    """
    cli_include_val: Any = args.include
    cli_include_list: Optional[list[str]] = None
    if isinstance(cli_include_val, list):
        cli_include_list = [str(p) for p in cli_include_val if isinstance(p, str)]

    config_include_val: Any = code_analysis_source_config.get("include_patterns", [])
    config_include_list: list[str] = (
        [str(p) for p in config_include_val if isinstance(p, str)] if isinstance(config_include_val, list) else []
    )
    effective_include_list = cli_include_list if cli_include_list is not None else config_include_list
    include_patterns: set[str] = set(effective_include_list)

    cli_exclude_val: Any = args.exclude
    cli_exclude_list: Optional[list[str]] = None
    if isinstance(cli_exclude_val, list):
        cli_exclude_list = [str(p) for p in cli_exclude_val if isinstance(p, str)]

    config_exclude_val: Any = code_analysis_source_config.get("default_exclude_patterns", [])
    config_exclude_list: list[str] = (
        [str(p) for p in config_exclude_val if isinstance(p, str)] if isinstance(config_exclude_val, list) else []
    )
    effective_exclude_list = cli_exclude_list if cli_exclude_list is not None else config_exclude_list
    exclude_patterns: set[str] = set(effective_exclude_list)

    return include_patterns, exclude_patterns


def _get_max_file_size_for_code_analysis(args: argparse.Namespace, code_analysis_source_config: dict[str, Any]) -> int:
    """Get the maximum file size for code analysis.

    Args:
        args: The `argparse.Namespace` object with command-line arguments.
        code_analysis_source_config: The 'source_config' part of the resolved
                                     'code_analysis' configuration.

    Returns:
        The maximum file size in bytes as an integer.
    """
    cli_max_size_val: Any = args.max_size
    if isinstance(cli_max_size_val, int) and cli_max_size_val >= 0:
        return cli_max_size_val

    config_max_size_val: Any = code_analysis_source_config.get("max_file_size_bytes")
    if isinstance(config_max_size_val, int) and config_max_size_val >= 0:
        return config_max_size_val
    return DEFAULT_MAX_FILE_SIZE_FALLBACK


def _determine_operation_mode(args: argparse.Namespace) -> str:
    """Determine the primary operation mode (code analysis or web analysis).

    Args:
        args: The `argparse.Namespace` object containing parsed command-line arguments.

    Returns:
        A string, either "code" or "web", indicating the determined operation mode.
    """
    if args.repo or args.dir:
        return "code"
    return "web"


def _prepare_initial_context(args: argparse.Namespace, processed_config: ConfigData) -> SharedContextDict:
    """Prepare the initial shared context dictionary for the processing flow.

    Args:
        args: The `argparse.Namespace` object containing parsed command-line arguments.
        processed_config: The loaded and processed application configuration dictionary.

    Returns:
        A `SharedContextDict` initialized with all necessary parameters.
    """
    common_settings: dict[str, Any] = processed_config.get("common", {})
    common_output_settings: dict[str, Any] = common_settings.get("common_output_settings", {})
    code_analysis_resolved: dict[str, Any] = processed_config.get("code_analysis", {"enabled": False})
    web_analysis_resolved: dict[str, Any] = processed_config.get("web_analysis", {"enabled": False})

    operation_mode = _determine_operation_mode(args)
    logger_main_prep = logging.getLogger(__name__)
    logger_main_prep.info("Operation mode determined: %s", operation_mode)

    output_name_cli_or_cfg = _get_output_name_from_cli_or_config(args, common_output_settings)
    final_output_name = _derive_name_from_source_if_auto(args, output_name_cli_or_cfg)

    current_llm_config: dict[str, Any] = {}
    current_mode_output_options: dict[str, Any] = {}

    if operation_mode == "code" and code_analysis_resolved.get("enabled"):
        current_llm_config = code_analysis_resolved.get("llm_config", {})
        current_mode_output_options = code_analysis_resolved.get("output_options", {})
    elif operation_mode == "web" and web_analysis_resolved.get("enabled"):
        current_llm_config = web_analysis_resolved.get("llm_config", {})
        current_mode_output_options = web_analysis_resolved.get("output_options", {})
    else:
        current_llm_config = common_settings.get("llm_default_options", {})

    cache_cfg: dict[str, Any] = common_settings.get("cache_settings", {})
    code_src_cfg_resolved: dict[str, Any] = code_analysis_resolved.get("source_config", {})
    inc_patterns_code, excl_patterns_code = _get_path_patterns_for_code_analysis(args, code_src_cfg_resolved)
    max_fsize_code = _get_max_file_size_for_code_analysis(args, code_src_cfg_resolved)
    use_rel_paths_code = bool(code_src_cfg_resolved.get("use_relative_paths", True))
    github_token_val: Any = code_analysis_resolved.get("github_token")
    github_token: Optional[str] = str(github_token_val) if isinstance(github_token_val, str) else None

    local_dir_str_val: Any = args.dir
    local_dir_str: Optional[str] = str(local_dir_str_val) if isinstance(local_dir_str_val, str) else None
    local_dir_disp_root = _get_local_dir_display_root(local_dir_str)

    main_out_dir_cli_val: Any = args.output
    main_out_dir_cli: Optional[str] = str(main_out_dir_cli_val) if isinstance(main_out_dir_cli_val, str) else None
    main_out_dir_cfg_val: Any = common_output_settings.get("main_output_directory")
    main_out_dir_cfg: str = str(main_out_dir_cfg_val) if isinstance(main_out_dir_cfg_val, str) else "output"
    main_out_dir: str = main_out_dir_cli or main_out_dir_cfg

    lang_cli_val: Any = args.language
    lang_cli: Optional[str] = str(lang_cli_val) if isinstance(lang_cli_val, str) else None
    lang_cfg_val: Any = common_output_settings.get("generated_text_language")
    lang_cfg: str = str(lang_cfg_val) if isinstance(lang_cfg_val, str) else "english"
    gen_text_lang: str = lang_cli or lang_cfg

    initial_context: SharedContextDict = {
        "config": processed_config,
        "llm_config": current_llm_config,
        "cache_config": cache_cfg,
        "project_name_override": args.name,
        "project_name": final_output_name,
        "output_dir": main_out_dir,
        "language": gen_text_lang,
        "repo_url": args.repo,
        "local_dir": local_dir_str,
        "crawl_url": args.crawl_url,
        "crawl_sitemap": args.crawl_sitemap,
        "crawl_file": args.crawl_file,
        "source_config": code_src_cfg_resolved if operation_mode == "code" else {},
        "github_token": github_token if operation_mode == "code" else None,
        "include_patterns": inc_patterns_code if operation_mode == "code" else set(),
        "exclude_patterns": excl_patterns_code if operation_mode == "code" else set(),
        "max_file_size": max_fsize_code if operation_mode == "code" else 0,
        "use_relative_paths": use_rel_paths_code if operation_mode == "code" else True,
        "local_dir_display_root": local_dir_disp_root if operation_mode == "code" else "",
        "cli_crawl_depth": args.crawl_depth,
        "cli_crawl_output_subdir": args.crawl_output_subdir,
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
        "current_mode_output_options": current_mode_output_options,
        "current_operation_mode": operation_mode,  # Added for FetchCode to know the context
    }
    logger_main_prep.debug(
        "Initial context prepared. Final output name: '%s'. Operation mode: '%s'", final_output_name, operation_mode
    )
    return initial_context


def _initialize_app(args: argparse.Namespace) -> ConfigData:
    """Load, validate, and process the application configuration, then set up logging.

    Args:
        args: The `argparse.Namespace` object containing parsed command-line arguments.

    Returns:
        A `ConfigData` dictionary representing the fully processed application configuration.

    Raises:
        SystemExit: If any critical error occurs during configuration or logging setup.
    """
    logger_init = logging.getLogger(__name__)
    config_data: ConfigData = {}
    validation_exceptions: tuple[type[Exception], ...] = (ConfigError,)

    try:
        config_path_str: str = str(args.config)
        config_data = load_config(config_path_str)

        common_config_val: Any = config_data.get("common", {})
        common_config: dict[str, Any] = common_config_val if isinstance(common_config_val, dict) else {}
        logging_settings_val: Any = common_config.get("logging", {})
        logging_settings: dict[str, Any] = logging_settings_val if isinstance(logging_settings_val, dict) else {}
        setup_logging(logging_settings)

        logger_init.info("Config loaded and processed successfully from %s", config_path_str)

        code_analysis_resolved: dict[str, Any] = config_data.get("code_analysis", {})
        if code_analysis_resolved.get("enabled"):
            logger_init.debug("Effective Code LLM Config: %s", code_analysis_resolved.get("llm_config"))
            logger_init.debug("Effective Source Config for Code: %s", code_analysis_resolved.get("source_config"))

        web_analysis_resolved: dict[str, Any] = config_data.get("web_analysis", {})
        if web_analysis_resolved.get("enabled"):
            logger_init.debug("Effective Web LLM Config: %s", web_analysis_resolved.get("llm_config"))
            logger_init.debug("Effective Crawler Options: %s", web_analysis_resolved.get("crawler_options"))

        logger_init.debug("Effective Common Output Settings: %s", common_config.get("common_output_settings"))
        return config_data
    except FileNotFoundError as e:
        print(f"ERROR (pre-logging): Configuration file not found: {e!s}", file=sys.stderr)
        logging.critical("Configuration file not found: %s", e)
        sys.exit(1)
    except validation_exceptions as e_val:
        print(f"ERROR (pre-logging): Config loading/validation failed: {e_val!s}", file=sys.stderr)
        logging.critical("Config loading/validation failed: %s", e_val, exc_info=True)
        sys.exit(1)
    except ImportError as e_imp:
        print(f"ERROR (pre-logging): Missing library for config: {e_imp!s}. Install dependencies.", file=sys.stderr)
        logging.critical("Missing required library for config: %s", e_imp)
        sys.exit(1)
    except OSError as e_os:
        print(f"ERROR (pre-logging): File system error: {e_os!s}", file=sys.stderr)
        logging.critical("File system error during config loading or logging setup: %s", e_os, exc_info=True)
        sys.exit(1)
    except (RuntimeError, ValueError, KeyError, TypeError) as e_prog:
        print(f"ERROR (pre-logging): Unexpected error: {e_prog!s}", file=sys.stderr)
        logging.critical("Unexpected error during config processing: %s", e_prog, exc_info=True)
        sys.exit(1)


def _log_run_flow_startup_info(initial_context: SharedContextDict) -> str:
    """Log essential startup information before running the processing flow.

    Args:
        initial_context: The `SharedContextDict` containing prepared data for the flow.

    Returns:
        A string indicating the operation mode ("code" or "web").
    """
    logger_run_flow = logging.getLogger(__name__)
    # operation_mode is now passed directly from _prepare_initial_context
    mode: str = str(initial_context.get("current_operation_mode", "unknown"))

    if mode == "web":
        source_val = (
            initial_context.get("crawl_url")
            or initial_context.get("crawl_sitemap")
            or initial_context.get("crawl_file")
        )
        source_description = str(source_val) if source_val is not None else "N/A"
        logger_run_flow.info("Starting web content analysis for: %s", source_description)
    elif mode == "code":
        source_val = initial_context.get("repo_url") or initial_context.get("local_dir")
        source_description = str(source_val) if source_val is not None else "N/A"
        logger_run_flow.info("Starting code analysis for: %s", source_description)
        code_source_cfg: dict[str, Any] = initial_context.get("source_config", {})
        lang_name = code_source_cfg.get("language_name_for_llm", "N/A")
        parser_type = code_source_cfg.get("parser_type", "N/A")
        logger_run_flow.info("Active Code Language Profile: %s (Parser: %s)", lang_name, parser_type)
    else:  # Should not happen if mode is always set
        logger_run_flow.error("Operation mode is '%s', which is unexpected. Review context setup.", mode)

    logger_run_flow.info("Output Name for this run: %s", initial_context.get("project_name"))
    logger_run_flow.info("Main Output Directory Base: %s", initial_context.get("output_dir"))
    logger_run_flow.info("Generated Text Language: %s", initial_context.get("language"))

    llm_cfg_for_log: dict[str, Any] = initial_context.get("llm_config", {})
    provider = llm_cfg_for_log.get("provider", "N/A")
    llm_type = "local" if llm_cfg_for_log.get("is_local_llm") else "cloud"
    model = llm_cfg_for_log.get("model", "N/A")
    logger_run_flow.info(f"Active LLM Provider for this '{mode}' mode: {provider} ({llm_type})")
    logger_run_flow.info(f"Active LLM Model for this '{mode}' mode: {model}")
    return mode


def _handle_flow_completion(initial_context: SharedContextDict, operation_mode: str) -> None:
    """Handle logging and printing messages after the main processing flow completes.

    Args:
        initial_context: The `SharedContextDict` after flow execution.
        operation_mode: A string ("code" or "web") indicating the analysis type.

    Raises:
        SystemExit: If no valid final output directory is confirmed.
    """
    logger_run_flow = logging.getLogger(__name__)
    final_dir_main_output_any: Any = initial_context.get("final_output_dir")
    final_output_path_confirmed: Optional[Path] = None
    msg_type: str = "Analysis"

    if final_dir_main_output_any and isinstance(final_dir_main_output_any, str):
        final_output_path_confirmed = Path(final_dir_main_output_any)
        msg_type = "Web summary" if operation_mode == "web" else "Code tutorial"
    elif operation_mode == "web":
        final_dir_crawl_raw_any: Any = initial_context.get("final_output_dir_web_crawl")
        if final_dir_crawl_raw_any and isinstance(final_dir_crawl_raw_any, str):
            final_output_path_confirmed = Path(final_dir_crawl_raw_any)
            msg_type = "Raw crawled web content (summary generation may have been skipped or failed)"
        else:
            logger_run_flow.error("Web flow finished, but no output directory was confirmed.")
    else:
        logger_run_flow.error("Code analysis flow finished, but no final output directory was confirmed.")

    if final_output_path_confirmed and final_output_path_confirmed.exists() and final_output_path_confirmed.is_dir():
        logger_run_flow.info("%s processing completed. Output in: %s", msg_type, final_output_path_confirmed.resolve())
        print(f"\n✅ {msg_type} processing complete! Files are in: {final_output_path_confirmed.resolve()}")
        return

    log_msg_fail = "Flow finished, but a valid final output directory was not confirmed or found."
    print(f"\n⚠️ ERROR: {log_msg_fail}", file=sys.stderr)
    logger_run_flow.error(log_msg_fail + f" (Operation Mode: {operation_mode})")
    sys.exit(1)


def _check_operation_mode_enabled(operation_mode: str, config: ConfigData) -> None:
    """Verify if the determined operation mode is enabled in the configuration, and exit if not.

    Args:
        operation_mode: The determined operation mode ("code" or "web").
        config: The fully processed application configuration.

    Raises:
        SystemExit: If the specified operation mode is disabled in the configuration.
    """
    logger_check = logging.getLogger(__name__)
    is_enabled = False
    if operation_mode == "code":
        is_enabled = config.get("code_analysis", {}).get("enabled", False)
    elif operation_mode == "web":
        is_enabled = config.get("web_analysis", {}).get("enabled", False)

    if not is_enabled:
        msg = f"Operation mode '{operation_mode}' is disabled in the configuration. Halting execution."
        logger_check.error(msg)
        print(f"\n❌ ERROR: {msg}", file=sys.stderr)
        sys.exit(1)


def _validate_flow_output_or_exit(initial_context: SharedContextDict, operation_mode: str) -> None:
    """Validate if essential output was generated by the flow, and exit if not.

    For 'code' mode, this function has been superseded by `NoFilesFetchedError`
    being raised by `FetchCode` and caught in `_run_flow`.
    For 'web' mode, it checks if either `initial_context["files"]` (for llm_extended)
    or `initial_context["final_output_dir_web_crawl"]` (for minimalistic) was set.

    Args:
        initial_context: The shared context after the flow has run.
        operation_mode: The current operation mode ("code" or "web").

    Raises:
        SystemExit: If crucial output is missing for web analysis, indicating a failure.
    """
    logger_val_flow = logging.getLogger(__name__)
    if operation_mode == "web":
        # Check if any files were processed or if a crawl directory was set
        # (FetchWebPage sets final_output_dir_web_crawl even if files list is empty for minimalistic)
        web_files_populated_for_llm_mode = bool(initial_context.get("files"))
        raw_crawl_output_dir_set = bool(initial_context.get("final_output_dir_web_crawl"))
        processing_mode_web = (
            initial_context.get("config", {}).get("web_analysis", {}).get("crawler_options", {}).get("processing_mode")
        )

        # If llm_extended, "files" should be populated.
        # If minimalistic, "final_output_dir_web_crawl" should be set if successful.
        # If neither is true, it implies FetchWebPage likely failed to produce any output.
        if (
            processing_mode_web == "llm_extended"
            and not web_files_populated_for_llm_mode
            and not raw_crawl_output_dir_set
        ):
            err_msg_web_l1 = "\n❌ ERROR: No web content was successfully fetched or processed for LLM analysis."
            err_msg_web_l2 = "       Please check the target URL/sitemap, network connection, and crawler options."
            print(err_msg_web_l1, file=sys.stderr)
            print(err_msg_web_l2, file=sys.stderr)
            logger_val_flow.error("Halting: No web content available after FetchWebPage for llm_extended mode.")
            sys.exit(1)
        elif processing_mode_web == "minimalistic" and not raw_crawl_output_dir_set:
            err_msg_web_l1 = "\n❌ ERROR: No web content was successfully fetched (minimalistic mode)."
            err_msg_web_l2 = "       The target directory for crawled files was not set. "
            err_msg_web_l3 = "       Check logs from FetchWebPage node."
            print(err_msg_web_l1, file=sys.stderr)
            print(err_msg_web_l2, file=sys.stderr)
            print(err_msg_web_l3, file=sys.stderr)
            logger_val_flow.error(
                "Halting: Raw crawl output directory not set after FetchWebPage in minimalistic mode."
            )
            sys.exit(1)
    # For 'code' mode, NoFilesFetchedError is now handled in the try-except block of _run_flow


def _run_flow(initial_context: SharedContextDict) -> None:
    """Create and execute the appropriate processing flow, with validation checks.

    Args:
        initial_context: The `SharedContextDict` for the flow.

    Raises:
        SystemExit: If the operation mode is disabled, critical output is missing
                    after flow execution, or an unrecoverable error occurs.
    """
    operation_mode = _log_run_flow_startup_info(initial_context)
    _check_operation_mode_enabled(operation_mode, initial_context.get("config", {}))

    try:
        llm_config_param: dict[str, Any] = initial_context.get("llm_config", {})
        cache_config_param: dict[str, Any] = initial_context.get("cache_config", {})

        if TYPE_CHECKING:
            from sourcelens.core.flow_engine_sync import Flow as RuntimeSourceLensFlowTyped  # type: ignore[no-redef]

            processing_flow_typed: RuntimeSourceLensFlowTyped
            processing_flow_typed = create_tutorial_flow(llm_config_param, cache_config_param, initial_context)
            processing_flow_typed.run_standalone(initial_context)
        else:
            from sourcelens.core.flow_engine_sync import Flow as RuntimeSourceLensFlow

            if RuntimeSourceLensFlow is None:
                raise RuntimeError("SourceLensFlow type could not be resolved at runtime.")
            processing_flow_runtime: Any = create_tutorial_flow(llm_config_param, cache_config_param, initial_context)
            processing_flow_runtime.run_standalone(initial_context)

        # Validation of output (e.g., if files were fetched) is now done after flow execution
        # or via NoFilesFetchedError for code analysis.
        # _validate_flow_output_or_exit is called after this try-except block if no exceptions occurred.

    except NoFilesFetchedError as e_no_files:
        logger_run_flow = logging.getLogger(__name__)
        err_msg_l1 = "\n❌ ERROR: No source files were found or matched the active configuration for code analysis."
        err_msg_l2 = (
            "       Please check your `config.json` (especially `active_language_profile_id`"
            " and its `include_patterns`)"
        )
        err_msg_l3 = "       or your CLI --include/--exclude arguments."
        print(err_msg_l1, file=sys.stderr)
        print(err_msg_l2, file=sys.stderr)
        print(err_msg_l3, file=sys.stderr)
        logger_run_flow.error("Halting due to NoFilesFetchedError: %s", e_no_files)
        sys.exit(1)
    except ImportError as e_imp_flow:
        logging.critical("Failed to import module during flow execution: %s", e_imp_flow, exc_info=True)
        print(f"\n❌ ERROR: Module import missing: {e_imp_flow!s}", file=sys.stderr)
        sys.exit(1)
    except (TypeError, RuntimeError, ConfigError, ValueError, KeyError, AttributeError) as e_flow:
        logging.critical("ERROR: Processing failed during flow execution: %s", e_flow, exc_info=True)
        print(f"\n❌ ERROR: Processing failed: {e_flow!s}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:  # Explicitly catch KeyboardInterrupt
        logging.warning("Execution interrupted by user (KeyboardInterrupt).")
        print("\n❌ Execution interrupted by user.", file=sys.stderr)
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e_unhandled:  # Catch-all for truly unexpected issues  # noqa: BLE001
        logging.critical("UNHANDLED EXCEPTION during flow execution: %s", e_unhandled, exc_info=True)
        print(f"\n❌ UNHANDLED ERROR: Processing failed unexpectedly: {e_unhandled!s}", file=sys.stderr)
        sys.exit(1)

    # If no exceptions were caught that caused an exit, proceed to validate output and complete.
    _validate_flow_output_or_exit(initial_context, operation_mode)
    _handle_flow_completion(initial_context, operation_mode=operation_mode)


def main() -> None:
    """Run the main command-line entry point for the SourceLens application.

    Orchestrates parsing arguments, initializing configuration and logging,
    preparing the initial shared context, and running the main processing flow.
    """
    args: argparse.Namespace = parse_arguments()
    loaded_config_data: ConfigData = _initialize_app(args)
    initial_shared_context: SharedContextDict = _prepare_initial_context(args, loaded_config_data)
    _run_flow(initial_shared_context)


if __name__ == "__main__":
    main()

# End of src/sourcelens/main.py
