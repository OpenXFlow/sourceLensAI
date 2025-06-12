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

"""Command-Line Interface for standalone execution of the Web Crawling Flow.

This script allows running the FL02_web_crawling flow independently,
primarily for testing, debugging, or specific use cases where only
web content analysis is required. It handles argument parsing,
configuration loading, logging setup, and execution of the web content
analysis pipeline, adhering to the new output directory structure.
"""

import argparse
import copy
import importlib
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional, Union, cast
from urllib.parse import urlparse

from typing_extensions import TypeAlias

from sourcelens.config_loader import (
    AUTO_DETECT_OUTPUT_NAME,
    DEFAULT_GENERATED_TEXT_LANGUAGE,
    DEFAULT_LOG_FORMAT_MAIN,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAIN_OUTPUT_DIR,
    DEFAULT_WEB_MAX_DEPTH_RECURSIVE,
    DEFAULT_WEB_PROCESSING_MODE,
    ConfigDict,
    ConfigError,
    ConfigLoader,
)
from sourcelens.utils.helpers import (
    get_youtube_video_title_and_id,
    is_youtube_url,
    sanitize_filename,
)

if TYPE_CHECKING:  # pragma: no cover
    from sourcelens.core import Flow as SourceLensFlow


logger: logging.Logger = logging.getLogger(__name__)

SharedContextDict: TypeAlias = dict[str, Any]
ResolvedFlowConfigData: TypeAlias = ConfigDict

_FLOW_NAME_CLI: Final[str] = "FL02_web_crawling"
_FLOW_DEFAULT_CONFIG_FILENAME_CLI: Final[str] = "config.default.json"
_GLOBAL_CONFIG_FILENAME_CLI: Final[str] = "config.json"

_FLOW_DEFAULT_LOG_FORMAT_STANDALONE_CLI: Final[str] = DEFAULT_LOG_FORMAT_MAIN
_DEFAULT_YT_BASE_NAME_CLI: Final[str] = "youtube_video"
_DEFAULT_WEB_BASE_NAME_CLI: Final[str] = "web_content"
_MAX_BASE_NAME_LEN_CLI: Final[int] = 50
_FLOW_DEFAULT_MAX_DEPTH_STANDALONE_CLI: Final[int] = DEFAULT_WEB_MAX_DEPTH_RECURSIVE


def parse_web_crawling_args() -> argparse.Namespace:
    """Parse command-line arguments specific to the Web Crawling Flow.

    Returns:
        argparse.Namespace: An object containing the parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description=f"Run SourceLens {_FLOW_NAME_CLI} independently.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--crawl-url", metavar="WEB_URL", help="Root URL of a website to crawl.")
    source_group.add_argument("--crawl-sitemap", metavar="SITEMAP_URL", help="URL of a sitemap.xml to crawl.")
    source_group.add_argument(
        "--crawl-file", metavar="FILE_URL_OR_PATH", help="URL or local path to a single text/markdown file."
    )

    parser.add_argument(
        "--flow-config",
        default=_FLOW_DEFAULT_CONFIG_FILENAME_CLI,
        metavar="FILE_PATH",
        type=Path,
        help="Path to the flow-specific JSON configuration file (relative to this script or absolute).",
    )
    parser.add_argument(
        "--global-config",
        default=None,
        metavar="FILE_PATH",
        type=Path,
        help=(
            f"Optional path to a global SourceLens '{_GLOBAL_CONFIG_FILENAME_CLI}'. "
            "If not provided, attempts to find it in parent dirs."
        ),
    )
    parser.add_argument(
        "-n", "--name", metavar="OUTPUT_NAME", help="Override auto-generated project name (timestamped base name)."
    )
    parser.add_argument(
        "-o", "--output", metavar="MAIN_OUTPUT_DIR", type=Path, help="Override main output directory from config."
    )
    parser.add_argument("--language", metavar="LANG", help="Override generated text language from config.")
    parser.add_argument("--crawl-depth", type=int, metavar="N", help="Max crawl recursion depth for web.")
    parser.add_argument(
        "--processing-mode",
        choices=["minimalistic", "llm_extended"],
        help="Override web content processing mode (minimalistic or llm_extended).",
        default=None,
    )
    # Hidden argument for audio extraction
    parser.add_argument(
        "--extract-audio",
        action="store_true",
        help=argparse.SUPPRESS,  # This hides the argument from the help message
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override logging level from config.",
    )
    parser.add_argument(
        "--log-file",
        metavar="PATH_OR_NONE",
        help="Path to log file for this run. Use 'NONE' to disable file logging.",
    )
    parser.add_argument("--llm-provider", metavar="ID", help="Override active LLM provider ID for this flow run.")
    parser.add_argument("--llm-model", metavar="NAME", help="Override LLM model name for this flow run.")
    parser.add_argument("--api-key", metavar="KEY", help="Override LLM API key for this flow run.")
    return parser.parse_args()


def setup_flow_logging(log_config: dict[str, Any]) -> None:
    """Set up basic logging for this flow's standalone execution.

    Args:
        log_config: A dictionary containing 'log_level' and 'log_file'.
    """
    log_level_str: str = str(log_config.get("log_level", DEFAULT_LOG_LEVEL)).upper()
    log_level_val: int = getattr(logging, log_level_str, logging.INFO)
    log_file_path_str: Optional[str] = log_config.get("log_file")
    log_file_to_use: Optional[Path] = None
    handlers_to_add: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file_path_str and log_file_path_str.upper() != "NONE":
        try:
            log_file_to_use = Path(log_file_path_str)
            log_file_to_use.parent.mkdir(parents=True, exist_ok=True)
            handlers_to_add.append(logging.FileHandler(log_file_to_use, encoding="utf-8", mode="a"))
            logger.info("Standalone flow logging to file: %s", log_file_to_use.resolve())
        except OSError as e_file_log:  # pragma: no cover
            print(f"WARNING: Could not set up file logger for flow: {e_file_log}", file=sys.stderr)
            logger.warning("File logging for flow disabled due to error. Using console only.")
    else:
        logger.info("File logging for standalone flow run is disabled.")

    logging.basicConfig(
        level=log_level_val,
        format=_FLOW_DEFAULT_LOG_FORMAT_STANDALONE_CLI,
        handlers=handlers_to_add,
        force=True,
    )
    logger.info("Logging initialized for %s standalone run at level %s.", _FLOW_NAME_CLI, log_level_str)


def _get_timestamp_prefix_cli() -> str:
    """Generate a timestamp prefix in YYYYMMDD_HHMM format for CLI runs.

    Returns:
        The formatted timestamp string.
    """
    return datetime.now().strftime("%Y%m%d_%H%M")


def _derive_base_name_and_type_prefix_for_web_source_cli(
    args: argparse.Namespace,
) -> tuple[str, str, Optional[str], Optional[str]]:
    """Derive a base name, type prefix, video ID, and title for web sources for CLI.

    Args:
        args: Parsed command-line arguments from the CLI.

    Returns:
        A tuple (base_name, type_prefix, video_id, video_title).
    """
    source_url_str: Optional[str] = None
    video_id: Optional[str] = None
    video_title: Optional[str] = None
    type_prefix: str = "_web_"
    base_name: str = _DEFAULT_WEB_BASE_NAME_CLI

    if args.crawl_url:
        source_url_str = str(args.crawl_url)
    elif args.crawl_sitemap:  # pragma: no cover
        source_url_str = str(args.crawl_sitemap)
    elif args.crawl_file:
        source_url_str = str(args.crawl_file)
    else:  # pragma: no cover
        return base_name, type_prefix, video_id, video_title

    if source_url_str:
        if is_youtube_url(source_url_str):
            fetched_id, fetched_title = get_youtube_video_title_and_id(source_url_str)
            if fetched_id:
                video_id = fetched_id
                video_title = fetched_title
                type_prefix = "_yt_"
                base_name = sanitize_filename(video_title or _DEFAULT_YT_BASE_NAME_CLI, max_len=_MAX_BASE_NAME_LEN_CLI)
        if type_prefix == "_web_":
            parsed_url_obj = urlparse(source_url_str)
            if parsed_url_obj.scheme and parsed_url_obj.netloc:
                base_name = sanitize_filename(
                    parsed_url_obj.netloc or Path(source_url_str).stem or _DEFAULT_WEB_BASE_NAME_CLI,
                    max_len=_MAX_BASE_NAME_LEN_CLI,
                )
            else:
                base_name = sanitize_filename(
                    Path(source_url_str).stem or _DEFAULT_WEB_BASE_NAME_CLI, max_len=_MAX_BASE_NAME_LEN_CLI
                )
    return base_name or _DEFAULT_WEB_BASE_NAME_CLI, type_prefix, video_id, video_title


def _derive_project_name_if_auto_cli(args: argparse.Namespace, current_name_from_config: str) -> str:
    """Derive project name if config indicates auto-detection for web flow CLI.

    The project name includes a timestamp prefix and a type prefix (e.g., _yt_, _web_).
    If `args.name` is provided, it overrides the auto-generated name.

    Args:
        args: Parsed command-line arguments.
        current_name_from_config: The current output name from configuration.

    Returns:
        The final project name for the run.
    """
    if args.name:
        return str(args.name)

    if current_name_from_config != AUTO_DETECT_OUTPUT_NAME:
        return current_name_from_config

    base_name, type_prefix, _video_id, _video_title = _derive_base_name_and_type_prefix_for_web_source_cli(args)
    timestamp_prefix = _get_timestamp_prefix_cli()
    return f"{timestamp_prefix}{type_prefix}{base_name}"


class DummyConfigLoaderForFlowCLI:
    """A simplified configuration loader for standalone web flow CLI execution."""

    _global_config_data: ConfigDict
    _logger_dummy: logging.Logger

    def __init__(self, global_config_path_str: Optional[str] = None) -> None:
        """Initialize the DummyConfigLoader for the web flow.

        Args:
            global_config_path_str: Optional path to a global configuration file.
        """
        self._logger_dummy = logging.getLogger(f"{__name__}.DummyConfigLoaderForFlowCLI")
        self._logger_dummy.setLevel(logging.DEBUG)
        if not self._logger_dummy.handlers:  # pragma: no cover
            _dummy_handler: logging.Handler = logging.StreamHandler(sys.stdout)
            _dummy_handler.setFormatter(logging.Formatter(_FLOW_DEFAULT_LOG_FORMAT_STANDALONE_CLI))
            self._logger_dummy.addHandler(_dummy_handler)
            self._logger_dummy.propagate = False

        self._global_config_data = {"common": {}, "profiles": {}}
        if global_config_path_str:  # pragma: no cover
            try:
                global_path: Path = Path(global_config_path_str).resolve(strict=True)
                self._global_config_data = self._read_json_file(global_path)
                self._logger_dummy.debug("DummyLoader: Loaded global config from %s", global_path)
            except (FileNotFoundError, ConfigError) as e_load_global:
                log_msg = f"DummyLoader: Could not load global config from '{global_config_path_str}': {e_load_global}."
                self._logger_dummy.warning("%s Using minimal global.", log_msg)
        else:
            self._logger_dummy.debug("DummyLoader: No global config path. Using minimal global.")

    def _read_json_file(self, fp: Path) -> ConfigDict:
        """Read and parse a JSON configuration file.

        Args:
            fp: Path object pointing to the JSON file.

        Returns:
            The loaded configuration as a dictionary.

        Raises:
            ConfigError: If file cannot be read, is not valid JSON, or root is not dict.
            TypeError: If loaded data is not a dictionary.
        """
        try:
            with fp.open("r", encoding="utf-8") as f_json:
                loaded_data: Any = json.load(f_json)
                if not isinstance(loaded_data, dict):  # pragma: no cover
                    raise TypeError(f"Configuration in {fp} is not a dictionary.")
                return cast(ConfigDict, loaded_data)
        except json.JSONDecodeError as e_json:  # pragma: no cover
            raise ConfigError(f"Invalid JSON syntax in '{fp}': {e_json!s}") from e_json
        except OSError as e_os:  # pragma: no cover
            raise ConfigError(f"Could not read configuration file '{fp}': {e_os!s}") from e_os

    def _deep_merge_configs(self, base: ConfigDict, override: ConfigDict) -> ConfigDict:
        """Deeply merge `override` into `base`. Modifies `base` in-place.

        Args:
            base: The base configuration dictionary (modified in-place).
            override: The dictionary whose values will override those in `base`.

        Returns:
            The modified `base` dictionary.
        """
        for k_merge, v_override_merge in override.items():
            if isinstance(v_override_merge, dict) and isinstance(base.get(k_merge), dict):
                self._deep_merge_configs(base[k_merge], v_override_merge)
            else:
                base[k_merge] = v_override_merge
        return base

    def _apply_simplified_cli_overrides(self, cfg: ConfigDict, cli_args: argparse.Namespace, flow_nm: str) -> None:
        """Apply simplified CLI overrides for the web dummy loader.

        Args:
            cfg: The configuration dictionary to modify.
            cli_args: Parsed command-line arguments.
            flow_nm: The name of the current flow (e.g., "FL02_web_crawling").
        """
        self._logger_dummy.debug("DummyLoader applying simplified CLI args to web config.")
        common_block_cfg: ConfigDict = cfg.setdefault("common", {})
        common_output_cfg: ConfigDict = common_block_cfg.setdefault("common_output_settings", {})
        logging_block_cfg: ConfigDict = common_block_cfg.setdefault("logging", {})
        flow_block_cfg: ConfigDict = cfg.setdefault(flow_nm, {})

        if getattr(cli_args, "output", None):
            common_output_cfg["main_output_directory"] = str(cli_args.output)
        if getattr(cli_args, "language", None):
            common_output_cfg["generated_text_language"] = cli_args.language
        if getattr(cli_args, "log_level", None):
            logging_block_cfg["log_level"] = cli_args.log_level
        if getattr(cli_args, "log_file", None):
            logging_block_cfg["log_file"] = str(cli_args.log_file)

        if flow_nm == _FLOW_NAME_CLI:
            crawler_opts_cfg: ConfigDict = flow_block_cfg.setdefault("crawler_options", {})
            if getattr(cli_args, "crawl_depth", None) is not None:
                crawler_opts_cfg["max_depth_recursive"] = cli_args.crawl_depth
            if getattr(cli_args, "processing_mode", None) is not None:
                crawler_opts_cfg["processing_mode"] = cli_args.processing_mode
            if getattr(cli_args, "llm_provider", None):
                flow_block_cfg["active_llm_provider_id"] = cli_args.llm_provider
            # Note: --extract-audio is not a config option, it's a direct flag for initial_context.

    def get_resolved_flow_config(
        self,
        flow_name: str,
        flow_default_config_path: Path,
        cli_args: Optional[argparse.Namespace] = None,
    ) -> ResolvedFlowConfigData:
        """Get resolved configuration for the web flow for standalone CLI.

        Args:
            flow_name: The name of the flow.
            flow_default_config_path: Path to `config.default.json` for the web flow.
            cli_args: Optional parsed command-line arguments.

        Returns:
            The merged and partially resolved configuration.
        """
        self._logger_dummy.info("DummyLoader resolving config for web flow: %s", flow_name)
        default_cfg: ConfigDict = self._read_json_file(flow_default_config_path)
        merged_cfg: ConfigDict = copy.deepcopy(default_cfg)
        self._logger_dummy.debug("DummyLoader: Loaded default flow config: %s", json.dumps(default_cfg, indent=2))

        merged_cfg_common: ConfigDict = merged_cfg.setdefault("common", {})
        global_common: ConfigDict = self._global_config_data.get("common", {})
        self._deep_merge_configs(merged_cfg_common, global_common)

        merged_cfg_profiles: ConfigDict = merged_cfg.setdefault("profiles", {})
        global_profiles: ConfigDict = self._global_config_data.get("profiles", {})
        merged_cfg_profiles.update(global_profiles)

        self._logger_dummy.debug(
            "DummyLoader: After merging global common/profiles: %s", json.dumps(merged_cfg, indent=2)
        )

        global_flow_overrides_cfg: ConfigDict = self._global_config_data.get(flow_name, {})
        if global_flow_overrides_cfg:
            merged_cfg_flow_block: ConfigDict = merged_cfg.setdefault(flow_name, {})
            self._deep_merge_configs(merged_cfg_flow_block, global_flow_overrides_cfg)
            self._logger_dummy.debug(
                "DummyLoader: After merging global flow-specific overrides: %s", json.dumps(merged_cfg, indent=2)
            )

        if cli_args:
            self._apply_simplified_cli_overrides(merged_cfg, cli_args, flow_name)
            self._logger_dummy.debug("DummyLoader: After applying CLI overrides: %s", json.dumps(merged_cfg, indent=2))

        llm_default_opts_cfg: ConfigDict = merged_cfg.get("common", {}).get("llm_default_options", {})
        active_llm_id_str: Optional[str] = cast(
            Optional[str], merged_cfg.get(flow_name, {}).get("active_llm_provider_id")
        )
        profiles_list_any: Any = merged_cfg.get("profiles", {}).get("llm_profiles", [])
        profiles_list: list[Any] = profiles_list_any if isinstance(profiles_list_any, list) else []

        resolved_llm_cfg: ConfigDict = copy.deepcopy(llm_default_opts_cfg)
        self._logger_dummy.debug("DummyLoader: Initial resolved_llm_cfg from defaults: %s", resolved_llm_cfg)

        if active_llm_id_str and isinstance(profiles_list, list):
            active_profile_found: Optional[dict[str, Any]] = next(
                (p for p in profiles_list if isinstance(p, dict) and p.get("provider_id") == active_llm_id_str), None
            )
            if active_profile_found:
                resolved_llm_cfg.update(active_profile_found)
                self._logger_dummy.debug(
                    "DummyLoader: Merged active profile '%s': %s", active_llm_id_str, active_profile_found
                )
                if cli_args and getattr(cli_args, "llm_model", None):
                    resolved_llm_cfg["model"] = cli_args.llm_model
                if cli_args and getattr(cli_args, "api_key", None):
                    resolved_llm_cfg["api_key"] = cli_args.api_key

        merged_cfg["resolved_llm_config"] = resolved_llm_cfg
        log_llm_safe: dict[str, Any] = {
            k: (v if k != "api_key" else ("***REDACTED***" if v else None)) for k, v in resolved_llm_cfg.items()
        }
        self._logger_dummy.debug("DummyLoader: Final resolved_llm_config: %s", json.dumps(log_llm_safe, indent=2))
        return cast(ResolvedFlowConfigData, merged_cfg)


def _initialize_flow_config_and_logging_logic(args: argparse.Namespace) -> ResolvedFlowConfigData:
    """Perform core logic for initializing config and logging for standalone web flow.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The fully resolved configuration dictionary.

    Raises:
        FileNotFoundError: If flow's default config not found.
        ConfigError: If error loading/processing configurations.
    """
    flow_default_path_arg: Path = args.flow_config
    flow_default_path: Path
    if not flow_default_path_arg.is_absolute():
        script_parent_dir: Path = Path(__file__).parent.resolve()
        flow_default_path = (script_parent_dir / flow_default_path_arg).resolve()
    else:
        flow_default_path = flow_default_path_arg.resolve()

    if not flow_default_path.is_file():
        raise FileNotFoundError(f"Flow default config not found: {flow_default_path}")

    loader: Union[ConfigLoader, DummyConfigLoaderForFlowCLI]
    global_config_path_to_use: Optional[str] = None

    if args.global_config:  # pragma: no cover
        global_config_path_to_use = str(args.global_config.resolve(strict=True))
        logger.info("Using explicit global config: %s", global_config_path_to_use)
        loader = ConfigLoader(global_config_path_to_use)
    else:
        current_dir = Path(__file__).parent.resolve()
        for _i in range(3):
            potential_global_config = current_dir / _GLOBAL_CONFIG_FILENAME_CLI
            if potential_global_config.is_file():
                global_config_path_to_use = str(potential_global_config)
                logger.info("Auto-detected global config at: %s", global_config_path_to_use)
                break
            if current_dir.parent == current_dir:
                break
            current_dir = current_dir.parent

        if global_config_path_to_use:  # pragma: no cover
            loader = ConfigLoader(global_config_path_to_use)
        else:
            logger.warning("No global config found. Using DummyConfigLoader.")
            loader = DummyConfigLoaderForFlowCLI(global_config_path_str=None)

    resolved_flow_config: ResolvedFlowConfigData = loader.get_resolved_flow_config(
        flow_name=_FLOW_NAME_CLI,
        flow_default_config_path=flow_default_path,
        cli_args=args,
    )

    common_config: dict[str, Any] = resolved_flow_config.get("common", {})
    logging_settings: dict[str, Any] = common_config.get("logging", {})
    setup_flow_logging(logging_settings)
    logger.info("%s CLI: Configuration loaded and processed.", _FLOW_NAME_CLI)
    return resolved_flow_config


def _initialize_flow_config_and_logging(args: argparse.Namespace) -> ResolvedFlowConfigData:
    """Initialize ConfigLoader, resolve config for web flow, and set up logging.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The fully resolved configuration for this flow.
    """
    try:
        return _initialize_flow_config_and_logging_logic(args)
    except (ConfigError, FileNotFoundError, ValueError, TypeError, AttributeError) as e_conf:  # pragma: no cover
        err_msg = f"ERROR: {_FLOW_NAME_CLI} CLI - Configuration setup failed: {e_conf!s}"
        print(err_msg, file=sys.stderr)
        if not logger.handlers:
            logging.basicConfig(level=logging.ERROR, format=_FLOW_DEFAULT_LOG_FORMAT_STANDALONE_CLI, stream=sys.stderr)
        logger.critical("Configuration error: %s", e_conf, exc_info=True)
        sys.exit(1)
    except (ImportError, RuntimeError, OSError) as e_unexpected:  # pragma: no cover
        err_msg = f"ERROR: {_FLOW_NAME_CLI} CLI - Unexpected error during init: {e_unexpected!s}"
        print(err_msg, file=sys.stderr)
        if not logger.handlers:
            logging.basicConfig(level=logging.ERROR, format=_FLOW_DEFAULT_LOG_FORMAT_STANDALONE_CLI, stream=sys.stderr)
        logger.critical("Unexpected initialization error: %s", e_unexpected, exc_info=True)
        sys.exit(1)


def _prepare_standalone_initial_context(
    args: argparse.Namespace, resolved_flow_config: ResolvedFlowConfigData
) -> SharedContextDict:
    """Prepare `initial_context` for a standalone web crawling and analysis run.

    Args:
        args: Parsed command-line arguments.
        resolved_flow_config: The fully resolved configuration.

    Returns:
        The initial context dictionary for the pipeline.
    """
    common_settings: dict[str, Any] = resolved_flow_config.get("common", {})
    common_output_settings: dict[str, Any] = common_settings.get("common_output_settings", {})
    flow_specific_settings: dict[str, Any] = resolved_flow_config.get(_FLOW_NAME_CLI, {})
    crawler_opts_from_resolved: dict[str, Any] = flow_specific_settings.get("crawler_options", {})

    output_name_cfg: str = str(common_output_settings.get("default_output_name", AUTO_DETECT_OUTPUT_NAME))
    final_project_name = _derive_project_name_if_auto_cli(args, output_name_cfg)
    _base_name, _type_prefix, yt_video_id, yt_video_title = _derive_base_name_and_type_prefix_for_web_source_cli(args)

    main_out_dir_cfg: str = str(common_output_settings.get("main_output_directory", DEFAULT_MAIN_OUTPUT_DIR))
    final_main_out_dir = str(args.output) if args.output else main_out_dir_cfg

    gen_text_lang_cfg: str = str(common_output_settings.get("generated_text_language", DEFAULT_GENERATED_TEXT_LANGUAGE))
    final_gen_text_lang = str(args.language) if args.language else gen_text_lang_cfg

    crawl_file_final: Optional[str] = None
    if args.crawl_file:
        crawl_file_str = str(args.crawl_file)
        if not is_youtube_url(crawl_file_str):
            try:
                p_crawl_file = Path(crawl_file_str)
                is_likely_path = os.sep in crawl_file_str or (os.path.altsep and os.path.altsep in crawl_file_str)
                if not urlparse(crawl_file_str).scheme and (
                    p_crawl_file.is_file() or (is_likely_path and not p_crawl_file.exists())
                ):  # pragma: no cover
                    crawl_file_final = str(p_crawl_file.resolve())
                else:  # pragma: no cover
                    crawl_file_final = crawl_file_str
            except (OSError, ValueError, TypeError) as e_path:  # pragma: no cover
                logger.warning("Error processing --crawl-file '%s': %s. Using raw string.", crawl_file_str, e_path)
                crawl_file_final = crawl_file_str
        else:
            crawl_file_final = crawl_file_str

    resolved_llm_config_ctx: ConfigDict = resolved_flow_config.get("resolved_llm_config", {})
    log_llm_ctx_safe = {k: (v if k != "api_key" else "***REDACTED***") for k, v in resolved_llm_config_ctx.items()}
    logger.debug(
        "Resolved LLM config for initial_context '%s': %s", _FLOW_NAME_CLI, json.dumps(log_llm_ctx_safe, indent=2)
    )

    # Ensure cli_extract_audio_enabled defaults to False if --extract-audio is not present
    cli_extract_audio_enabled = getattr(args, "extract_audio", False)

    initial_context: SharedContextDict = {
        "config": resolved_flow_config,
        "llm_config": resolved_llm_config_ctx,
        "cache_config": common_settings.get("cache_settings", {}),
        "project_name": final_project_name,
        "output_dir": final_main_out_dir,
        "language": final_gen_text_lang,
        "current_operation_mode": _FLOW_NAME_CLI,
        "current_mode_output_options": flow_specific_settings.get("output_options", {}),
        "crawl_url": args.crawl_url,
        "crawl_sitemap": args.crawl_sitemap,
        "crawl_file": crawl_file_final,
        "current_youtube_video_id": yt_video_id,
        "current_youtube_video_title": yt_video_title,
        "current_youtube_sanitized_title": sanitize_filename(yt_video_title or "", max_len=_MAX_BASE_NAME_LEN_CLI)
        if yt_video_title
        else None,
        "cli_crawl_depth": crawler_opts_from_resolved.get(
            "max_depth_recursive", _FLOW_DEFAULT_MAX_DEPTH_STANDALONE_CLI
        ),
        "processing_mode": crawler_opts_from_resolved.get("processing_mode", DEFAULT_WEB_PROCESSING_MODE),
        "cli_extract_audio_enabled": cli_extract_audio_enabled,  # Add the new flag
        "files": [],
        "web_content_chunks": [],
        "text_concepts": [],
        "text_relationships": {},
        "text_chapter_order": [],
        "text_chapters": [],
        "content_inventory_md": None,
        "web_content_review_md": None,
        "final_output_dir": None,
        "final_output_dir_web_crawl": None,
        "youtube_processed_successfully": False,
        "current_youtube_original_lang": None,
        "current_youtube_standalone_transcript_path": None,
        "current_youtube_url": args.crawl_url if is_youtube_url(str(args.crawl_url or "")) else None,
        "current_youtube_final_transcript_lang": None,
        "current_youtube_final_transcript_path": None,
    }
    logger.debug("Standalone initial context for %s prepared.", _FLOW_NAME_CLI)
    return initial_context


def run_standalone_web_crawling() -> None:
    """Run the web crawling and analysis flow independently as a standalone script."""
    args: argparse.Namespace = parse_web_crawling_args()
    resolved_config: ResolvedFlowConfigData = _initialize_flow_config_and_logging(args)
    initial_context: SharedContextDict = _prepare_standalone_initial_context(args, resolved_config)

    logger.info("Starting %s flow (standalone)...", _FLOW_NAME_CLI)
    final_flow_settings_log_val: Any = initial_context.get("config", {}).get(_FLOW_NAME_CLI, {})
    final_flow_settings_log: ConfigDict = (
        final_flow_settings_log_val if isinstance(final_flow_settings_log_val, dict) else {}
    )
    logger.debug(
        "Effective runtime flow config '%s': %s",
        _FLOW_NAME_CLI,
        json.dumps(final_flow_settings_log, indent=2, default=str),
    )

    final_common_settings_log_val: Any = initial_context.get("config", {}).get("common", {})
    final_common_settings_log: ConfigDict = (
        final_common_settings_log_val if isinstance(final_common_settings_log_val, dict) else {}
    )
    logger.debug(
        "Effective common settings for '%s': %s",
        _FLOW_NAME_CLI,
        json.dumps(final_common_settings_log, indent=2, default=str),
    )

    final_llm_config_log_val: Any = initial_context.get("llm_config", {})
    final_llm_config_log: ConfigDict = final_llm_config_log_val if isinstance(final_llm_config_log_val, dict) else {}
    log_llm_safe = {k: (v if k != "api_key" else "***REDACTED***") for k, v in final_llm_config_log.items()}
    logger.debug("Effective LLM config for '%s': %s", _FLOW_NAME_CLI, json.dumps(log_llm_safe, indent=2, default=str))

    try:
        flow_module_path = "FL02_web_crawling.flow"
        flow_module = importlib.import_module(flow_module_path)
        create_web_crawling_flow_func = getattr(flow_module, "create_web_crawling_flow")

        web_pipeline: "SourceLensFlow" = create_web_crawling_flow_func(initial_context)
        logger.info("Web crawling pipeline created. Running...")
        web_pipeline.run_standalone(initial_context)
        logger.info("Web crawling pipeline finished successfully.")

        final_dir_key_main = "final_output_dir"
        final_dir_key_crawl = "final_output_dir_web_crawl"

        final_dir_val: Optional[str] = None
        output_msg_type: str = "Analysis"

        if initial_context.get(final_dir_key_main):
            final_dir_val = str(initial_context[final_dir_key_main])
            output_msg_type = "Web summary/tutorial"
        elif initial_context.get(final_dir_key_crawl):
            final_dir_val = str(initial_context[final_dir_key_crawl])
            if initial_context.get("processing_mode") == "minimalistic":
                output_msg_type = "Raw crawled content (summary/tutorial generation skipped)"
            else:
                output_msg_type = "Raw crawled content"

        if final_dir_val:
            print(f"\n✅ Standalone {output_msg_type} processing complete! Output in: {Path(final_dir_val).resolve()}")
        else:  # pragma: no cover
            print("\n⚠️ Standalone web analysis finished, but no output directory was set in context.")

    except (
        ConfigError,
        ValueError,
        TypeError,
        AttributeError,
        RuntimeError,
        OSError,
        ImportError,
    ) as e_flow:  # pragma: no cover
        logger.critical("Error during standalone web crawling pipeline execution: %s", e_flow, exc_info=True)
        print(f"\n❌ ERROR: Pipeline execution failed: {e_flow!s}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:  # pragma: no cover
        logger.warning("Standalone web crawling execution interrupted by user.")
        print("\n❌ Execution interrupted by user.", file=sys.stderr)
        sys.exit(130)

    logger.info("%s flow (standalone) finished processing.", _FLOW_NAME_CLI)


if __name__ == "__main__":  # pragma: no cover
    run_standalone_web_crawling()

# End of src/FL02_web_crawling/cli.py
