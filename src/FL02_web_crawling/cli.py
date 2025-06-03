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
configuration loading (potentially merging with a global config),
logging setup, and execution of the web content analysis pipeline.
"""

import argparse
import copy
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional, Union, cast
from urllib.parse import urlparse

from typing_extensions import TypeAlias

from sourcelens.config_loader import (
    AUTO_DETECT_OUTPUT_NAME,
    DEFAULT_GENERATED_TEXT_LANGUAGE,
    DEFAULT_LOG_FORMAT_MAIN,  # Správny import
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAIN_OUTPUT_DIR,
    DEFAULT_WEB_MAX_DEPTH_RECURSIVE,
    DEFAULT_WEB_OUTPUT_SUBDIR_NAME,
    DEFAULT_WEB_PROCESSING_MODE,
    ConfigDict,
    ConfigError,
    ConfigLoader,
)
from sourcelens.utils.helpers import sanitize_filename

if TYPE_CHECKING:
    from sourcelens.core import Flow as SourceLensFlow


logger: logging.Logger = logging.getLogger(__name__)

SharedContextDict: TypeAlias = dict[str, Any]
ResolvedFlowConfigData: TypeAlias = ConfigDict

_FLOW_NAME: Final[str] = "FL02_web_crawling"
_FLOW_DEFAULT_CONFIG_FILENAME: Final[str] = "config.default.json"
_GLOBAL_CONFIG_FILENAME: Final[str] = "config.json"

_FLOW_DEFAULT_LOG_FORMAT_CLI: Final[str] = DEFAULT_LOG_FORMAT_MAIN
_FLOW_DEFAULT_OUTPUT_NAME_CLI: Final[str] = f"{DEFAULT_WEB_PROCESSING_MODE}-web-analysis"
# _FLOW_DEFAULT_OUTPUT_DIR_CLI: Final[str] = DEFAULT_MAIN_OUTPUT_DIR
# _FLOW_DEFAULT_LANGUAGE_CLI: Final[str] = DEFAULT_GENERATED_TEXT_LANGUAGE
_FLOW_DEFAULT_MAX_DEPTH_CLI: Final[int] = DEFAULT_WEB_MAX_DEPTH_RECURSIVE
_FLOW_DEFAULT_CRAWL_SUBDIR_CLI: Final[str] = DEFAULT_WEB_OUTPUT_SUBDIR_NAME

_FLOW_MAX_PROJECT_NAME_LEN_CLI: Final[int] = 40


def parse_web_crawling_args() -> argparse.Namespace:
    """Parse command-line arguments specific to the Web Crawling Flow.

    Defines and parses arguments for specifying web content sources (URL, sitemap,
    or file), configuration files, output naming and location, crawl parameters,
    logging levels, and LLM provider overrides for a standalone run.

    Returns:
        argparse.Namespace: An object containing the parsed command-line arguments.
                            Each argument is accessible as an attribute of this object.
    """
    parser = argparse.ArgumentParser(
        description=f"Run SourceLens {_FLOW_NAME} independently.",
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
        default=_FLOW_DEFAULT_CONFIG_FILENAME,
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
            f"Optional path to a global SourceLens '{_GLOBAL_CONFIG_FILENAME}'. "
            "If not provided, attempts to find it in parent dirs."
        ),
    )
    parser.add_argument("-n", "--name", metavar="OUTPUT_NAME", help="Override default output name from config.")
    parser.add_argument(
        "-o", "--output", metavar="MAIN_OUTPUT_DIR", type=Path, help="Override main output directory from config."
    )
    parser.add_argument("--language", metavar="LANG", help="Override generated text language from config.")
    parser.add_argument("--crawl-depth", type=int, metavar="N", help="Max crawl recursion depth for web.")
    parser.add_argument("--crawl-output-subdir", metavar="NAME", help="Subdir name for raw crawled web content.")
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

    Configures logging to stream to stdout and optionally to a file,
    based on the resolved logging level and log file path from `log_config`.

    Args:
        log_config (dict[str, Any]): A dictionary containing logging configuration.
                                     Expected keys: 'log_level' (str), 'log_file' (Optional[str]).
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
        except OSError as e_file_log:
            print(f"WARNING: Could not set up file logger for flow: {e_file_log}", file=sys.stderr)
            logger.warning("File logging for flow disabled due to error. Using console only.")
    else:
        logger.info("File logging for standalone flow run is disabled.")

    logging.basicConfig(
        level=log_level_val,
        format=_FLOW_DEFAULT_LOG_FORMAT_CLI,
        handlers=handlers_to_add,
        force=True,
    )
    logger.info("Logging initialized for %s standalone run at level %s.", _FLOW_NAME, log_level_str)


def _derive_name_from_web_source_cli(args: argparse.Namespace) -> str:
    """Derive an output name for web sources based on URL or filename.

    Prioritizes crawl URL, then sitemap URL, then file path/URL.
    The derived name is sanitized for use in filenames.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
                                   Expected to have `crawl_url`, `crawl_sitemap`,
                                   or `crawl_file` attributes.

    Returns:
        str: A sanitized, derived name suitable for output identification.
             Returns a default name if derivation fails.
    """
    source_val: Any = args.crawl_url or args.crawl_sitemap or args.crawl_file
    name_candidate: str = ""

    if source_val:
        source_str: str = str(source_val)
        try:
            parsed_url_obj = urlparse(source_str)
            if parsed_url_obj.scheme and parsed_url_obj.netloc:
                name_candidate = parsed_url_obj.netloc or Path(parsed_url_obj.path).stem
            else:
                name_candidate = Path(source_str).stem
            if name_candidate:
                return sanitize_filename(name_candidate, max_len=_FLOW_MAX_PROJECT_NAME_LEN_CLI)
        except (ValueError, TypeError, AttributeError, OSError) as e:
            logger.warning("Could not derive name from web source '%s': %s", source_str, e)
    return _FLOW_DEFAULT_OUTPUT_NAME_CLI


def _derive_name_if_auto_cli(args: argparse.Namespace, current_name: str) -> str:
    """Derive output name if the current name indicates auto-detection for web flow.

    If `current_name` is `AUTO_DETECT_OUTPUT_NAME`, this function attempts to derive
    a name from the web source specified in CLI arguments. If the user provided
    a `--name` via CLI, that takes precedence.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        current_name (str): The current output name, typically from configuration.

    Returns:
        str: The final output name.
    """
    if current_name != AUTO_DETECT_OUTPUT_NAME:
        return current_name
    if args.name:
        return str(args.name)
    derived = _derive_name_from_web_source_cli(args)
    return derived or _FLOW_DEFAULT_OUTPUT_NAME_CLI


class DummyConfigLoaderForFlowCLI:
    """A simplified configuration loader for standalone web flow CLI execution.

    This loader is used when a global SourceLens configuration file is not
    provided or found. It loads the web flow's default configuration and merges
    it with a minimal global structure, applying basic CLI argument overrides
    relevant to web crawling.
    """

    _global_config_data: ConfigDict
    _logger_dummy: logging.Logger

    def __init__(self, global_config_path_str: Optional[str] = None) -> None:
        """Initialize the DummyConfigLoader for the web flow.

        Args:
            global_config_path_str (Optional[str]): Optional path to a global configuration file.
        """
        self._logger_dummy = logging.getLogger(f"{__name__}.DummyConfigLoaderForFlowCLI")
        self._logger_dummy.setLevel(logging.DEBUG)
        if not self._logger_dummy.handlers:
            _dummy_handler = logging.StreamHandler(sys.stdout)
            _dummy_handler.setFormatter(logging.Formatter(_FLOW_DEFAULT_LOG_FORMAT_CLI))
            self._logger_dummy.addHandler(_dummy_handler)
            self._logger_dummy.propagate = False

        self._global_config_data = {"common": {}, "profiles": {}}
        if global_config_path_str:
            try:
                global_path = Path(global_config_path_str).resolve(strict=True)
                self._global_config_data = self._read_json_file(global_path)
                self._logger_dummy.debug("DummyLoader: Successfully loaded global config from %s", global_path)
            except (FileNotFoundError, ConfigError) as e_load_global:
                log_msg_part1 = f"DummyLoader: Could not load global config from '{global_config_path_str}': "
                log_msg_part2 = f"{e_load_global}. Using minimal global."
                self._logger_dummy.warning(log_msg_part1 + log_msg_part2)
        else:
            self._logger_dummy.debug("DummyLoader: No global config path provided. Using minimal global structure.")

    def _read_json_file(self, fp: Path) -> ConfigDict:
        """Read and parse a JSON configuration file.

        Args:
            fp (Path): Path object pointing to the JSON file.

        Returns:
            ConfigDict: The loaded configuration as a dictionary.

        Raises:
            ConfigError: If the file cannot be read, is not valid JSON,
                         or the root JSON structure is not a dictionary.
            TypeError: If the loaded data is not a dictionary.
        """
        try:
            with fp.open("r", encoding="utf-8") as f_json:
                loaded_data: Any = json.load(f_json)
                if not isinstance(loaded_data, dict):
                    raise TypeError(f"Configuration in {fp} is not a dictionary.")
                return cast(ConfigDict, loaded_data)
        except json.JSONDecodeError as e_json:
            raise ConfigError(f"Invalid JSON syntax in '{fp}': {e_json!s}") from e_json
        except OSError as e_os:
            raise ConfigError(f"Could not read configuration file '{fp}': {e_os!s}") from e_os

    def _deep_merge_configs(self, base: ConfigDict, override: ConfigDict) -> ConfigDict:
        """Deeply merge `override` into `base`. Modifies `base` in-place.

        Args:
            base (ConfigDict): The base configuration dictionary (modified in-place).
            override (ConfigDict): The dictionary whose values will override those in `base`.

        Returns:
            ConfigDict: The modified `base` dictionary.
        """
        for k, v_override in override.items():
            if isinstance(v_override, dict) and isinstance(base.get(k), dict):
                self._deep_merge_configs(base[k], v_override)
            else:
                base[k] = v_override
        return base

    def _apply_simplified_cli_overrides(self, cfg: ConfigDict, cli_args: argparse.Namespace, flow_nm: str) -> None:
        """Apply simplified CLI overrides for the web dummy loader.

        Args:
            cfg (ConfigDict): The configuration dictionary to modify.
            cli_args (argparse.Namespace): Parsed command-line arguments.
            flow_nm (str): The name of the current flow (e.g., "FL02_web_crawling").
        """
        self._logger_dummy.debug("DummyLoader applying simplified CLI args to web config.")
        common_block = cfg.setdefault("common", {})
        common_output = common_block.setdefault("common_output_settings", {})
        logging_block = common_block.setdefault("logging", {})
        flow_block = cfg.setdefault(flow_nm, {})

        if getattr(cli_args, "name", None):
            common_output["default_output_name"] = cli_args.name
        if getattr(cli_args, "output", None):
            common_output["main_output_directory"] = str(cli_args.output)
        if getattr(cli_args, "language", None):
            common_output["generated_text_language"] = cli_args.language
        if getattr(cli_args, "log_level", None):
            logging_block["log_level"] = cli_args.log_level
        if getattr(cli_args, "log_file", None):
            logging_block["log_file"] = str(cli_args.log_file)

        if flow_nm == _FLOW_NAME:
            crawler_opts = flow_block.setdefault("crawler_options", {})
            if getattr(cli_args, "crawl_depth", None) is not None:
                crawler_opts["max_depth_recursive"] = cli_args.crawl_depth
            if getattr(cli_args, "crawl_output_subdir", None):
                crawler_opts["default_output_subdir_name"] = cli_args.crawl_output_subdir
            if getattr(cli_args, "llm_provider", None):
                flow_block["active_llm_provider_id"] = cli_args.llm_provider

    def get_resolved_flow_config(
        self,
        flow_name: str,
        flow_default_config_path: Path,
        cli_args: Optional[argparse.Namespace] = None,
    ) -> ResolvedFlowConfigData:
        """Get resolved configuration for the web flow for standalone CLI.

        Args:
            flow_name (str): The name of the flow (e.g., "FL02_web_crawling").
            flow_default_config_path (Path): Path to `config.default.json` for the web flow.
            cli_args (Optional[argparse.Namespace]): Optional parsed command-line arguments.

        Returns:
            ResolvedFlowConfigData: The merged and partially resolved configuration.
        """
        self._logger_dummy.info("DummyLoader resolving config for web flow: %s", flow_name)
        default_cfg = self._read_json_file(flow_default_config_path)
        merged_cfg = copy.deepcopy(default_cfg)
        self._logger_dummy.debug("DummyLoader: Loaded default flow config: %s", json.dumps(default_cfg, indent=2))

        self._deep_merge_configs(merged_cfg.setdefault("common", {}), self._global_config_data.get("common", {}))
        merged_cfg.setdefault("profiles", {}).update(self._global_config_data.get("profiles", {}))
        self._logger_dummy.debug(
            "DummyLoader: After merging global common/profiles: %s", json.dumps(merged_cfg, indent=2)
        )

        global_flow_overrides = self._global_config_data.get(flow_name, {})
        if global_flow_overrides:
            merged_cfg_flow_block = merged_cfg.setdefault(flow_name, {})
            self._deep_merge_configs(merged_cfg_flow_block, global_flow_overrides)
            self._logger_dummy.debug(
                "DummyLoader: After merging global flow-specific overrides: %s", json.dumps(merged_cfg, indent=2)
            )

        if cli_args:
            self._apply_simplified_cli_overrides(merged_cfg, cli_args, flow_name)
            self._logger_dummy.debug("DummyLoader: After applying CLI overrides: %s", json.dumps(merged_cfg, indent=2))

        llm_default_opts = merged_cfg.get("common", {}).get("llm_default_options", {})
        active_llm_id = merged_cfg.get(flow_name, {}).get("active_llm_provider_id")
        profiles = merged_cfg.get("profiles", {}).get("llm_profiles", [])
        resolved_llm_cfg = copy.deepcopy(llm_default_opts)
        self._logger_dummy.debug("DummyLoader: Initial resolved_llm_cfg from defaults: %s", resolved_llm_cfg)

        if active_llm_id and isinstance(active_llm_id, str) and isinstance(profiles, list):
            active_profile = next(
                (p for p in profiles if isinstance(p, dict) and p.get("provider_id") == active_llm_id), None
            )
            if active_profile:
                resolved_llm_cfg.update(active_profile)
                self._logger_dummy.debug("DummyLoader: Merged active profile '%s': %s", active_llm_id, active_profile)
                if cli_args and getattr(cli_args, "llm_model", None):
                    resolved_llm_cfg["model"] = cli_args.llm_model
                    self._logger_dummy.debug("DummyLoader: CLI override model to: %s", cli_args.llm_model)
                if cli_args and getattr(cli_args, "api_key", None):
                    resolved_llm_cfg["api_key"] = cli_args.api_key
                    self._logger_dummy.debug("DummyLoader: CLI override api_key (value redacted).")

        merged_cfg["resolved_llm_config"] = resolved_llm_cfg
        log_llm_config_dummy_safe = {
            k: (v if k != "api_key" else ("***REDACTED***" if v else None)) for k, v in resolved_llm_cfg.items()
        }
        self._logger_dummy.debug(
            "DummyLoader: Final resolved_llm_config: %s", json.dumps(log_llm_config_dummy_safe, indent=2, default=str)
        )
        return cast(ResolvedFlowConfigData, merged_cfg)


def _initialize_flow_config_and_logging_logic(args: argparse.Namespace) -> ResolvedFlowConfigData:
    """Perform the core logic for initializing configuration and logging for standalone web flow.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The fully resolved configuration dictionary specific
        to the web analysis flow to be executed.

    Raises:
        FileNotFoundError: If the flow's default configuration file is not found.
        ConfigError: If there's an error loading or processing configurations.
    """
    flow_default_path_arg: Path = args.flow_config
    if not flow_default_path_arg.is_absolute():
        script_parent_dir = Path(__file__).parent.resolve()
        flow_default_path = (script_parent_dir / flow_default_path_arg).resolve()
    else:
        flow_default_path = flow_default_path_arg.resolve()

    if not flow_default_path.is_file():
        raise FileNotFoundError(f"Flow default config not found: {flow_default_path}")

    loader: Union[ConfigLoader, DummyConfigLoaderForFlowCLI]
    global_config_path_to_use: Optional[str] = None

    if args.global_config:
        global_config_path_to_use = str(args.global_config.resolve(strict=True))
        logger.info("Using explicit global config: %s", global_config_path_to_use)
        loader = ConfigLoader(global_config_path_to_use)
    else:
        current_dir = Path(__file__).parent.resolve()
        for _i in range(3):
            potential_global_config = current_dir / _GLOBAL_CONFIG_FILENAME
            if potential_global_config.is_file():
                global_config_path_to_use = str(potential_global_config)
                logger.info("Auto-detected global config at: %s", global_config_path_to_use)
                break
            if current_dir.parent == current_dir:
                break
            current_dir = current_dir.parent
        if global_config_path_to_use:
            loader = ConfigLoader(global_config_path_to_use)
        else:
            logger.warning(
                "No global config found or specified. Using DummyConfigLoader "
                "with flow defaults and minimal global structure."
            )
            loader = DummyConfigLoaderForFlowCLI(global_config_path_str=None)

    resolved_flow_config = loader.get_resolved_flow_config(
        flow_name=_FLOW_NAME,
        flow_default_config_path=flow_default_path,
        cli_args=args,
    )

    common_config_resolved: dict[str, Any] = resolved_flow_config.get("common", {})
    logging_settings_resolved: dict[str, Any] = common_config_resolved.get("logging", {})
    setup_flow_logging(logging_settings_resolved)
    logger.info("%s CLI: Configuration loaded and processed.", _FLOW_NAME)
    return resolved_flow_config


def _initialize_flow_config_and_logging(args: argparse.Namespace) -> ResolvedFlowConfigData:
    """Initialize ConfigLoader, resolve config for web flow, and set up logging.

    This function acts as a wrapper around `_initialize_flow_config_and_logging_logic`
    to provide centralized error handling for critical configuration and logging setup failures.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The fully resolved configuration for this flow.

    Raises:
        SystemExit: If configuration or logging setup fails critically.
    """
    try:
        return _initialize_flow_config_and_logging_logic(args)
    except (ConfigError, FileNotFoundError, ValueError, TypeError, AttributeError) as e_conf:
        print(f"ERROR: {_FLOW_NAME} CLI - Configuration setup failed: {e_conf!s}", file=sys.stderr)
        if not logger.handlers:
            logging.basicConfig(level=logging.ERROR, format=_FLOW_DEFAULT_LOG_FORMAT_CLI, stream=sys.stderr)
        logger.critical("Configuration error: %s", e_conf, exc_info=True)
        sys.exit(1)
    except (ImportError, RuntimeError, OSError) as e_unexpected:  # pragma: no cover
        print(f"ERROR: {_FLOW_NAME} CLI - Unexpected error during init: {e_unexpected!s}", file=sys.stderr)
        if not logger.handlers:
            logging.basicConfig(level=logging.ERROR, format=_FLOW_DEFAULT_LOG_FORMAT_CLI, stream=sys.stderr)
        logger.critical("Unexpected initialization error: %s", e_unexpected, exc_info=True)
        sys.exit(1)


def _prepare_standalone_initial_context(
    args: argparse.Namespace, resolved_flow_config: ResolvedFlowConfigData
) -> SharedContextDict:
    """Prepare `initial_context` for a standalone web crawling and analysis run.

    Populates the context with values from CLI arguments and the resolved
    configuration, setting up all keys expected by the web analysis flow.

    Args:
        args: Parsed command-line arguments.
        resolved_flow_config: The fully resolved configuration specific to this
                              web analysis flow.

    Returns:
        The initial context dictionary for the pipeline.
    """
    common_settings: dict[str, Any] = resolved_flow_config.get("common", {})
    common_output_settings: dict[str, Any] = common_settings.get("common_output_settings", {})
    flow_specific_settings: dict[str, Any] = resolved_flow_config.get(_FLOW_NAME, {})

    output_name_from_config = str(common_output_settings.get("default_output_name", AUTO_DETECT_OUTPUT_NAME))
    final_output_name = _derive_name_if_auto_cli(args, output_name_from_config)

    main_out_dir_from_config = str(common_output_settings.get("main_output_directory", DEFAULT_MAIN_OUTPUT_DIR))
    final_main_out_dir = str(args.output) if args.output else main_out_dir_from_config

    gen_text_lang_from_config = str(
        common_output_settings.get("generated_text_language", DEFAULT_GENERATED_TEXT_LANGUAGE)
    )
    final_gen_text_lang = str(args.language) if args.language else gen_text_lang_from_config

    crawler_opts_from_resolved_config = flow_specific_settings.get("crawler_options", {})

    crawl_file_final: Optional[str] = None
    if args.crawl_file:
        crawl_file_str = str(args.crawl_file)
        try:
            p_crawl_file = Path(crawl_file_str)
            is_likely_path = os.sep in crawl_file_str or (os.path.altsep and os.path.altsep in crawl_file_str)
            if not urlparse(crawl_file_str).scheme and (
                p_crawl_file.is_file() or (is_likely_path and not p_crawl_file.exists())
            ):
                if p_crawl_file.is_file():
                    crawl_file_final = str(p_crawl_file.resolve())
                else:
                    logger.warning(
                        "Local crawl file path '%s' does not exist or is not a file. Using as raw string.",
                        crawl_file_str,
                    )
                    crawl_file_final = crawl_file_str
            else:
                crawl_file_final = crawl_file_str
        except Exception:  # pragma: no cover
            logger.error(
                "Error processing --crawl-file argument '%s'. Using as raw string.", crawl_file_str, exc_info=True
            )
            crawl_file_final = crawl_file_str

    resolved_llm_config_for_context = resolved_flow_config.get("resolved_llm_config", {})
    logger.debug(
        "Resolved LLM config to be used in initial_context for flow '%s': %s",
        _FLOW_NAME,
        json.dumps(
            {k: (v if k != "api_key" else "***REDACTED***") for k, v in resolved_llm_config_for_context.items()},
            indent=2,
        ),
    )

    initial_context: SharedContextDict = {
        "config": resolved_flow_config,
        "llm_config": resolved_llm_config_for_context,
        "cache_config": common_settings.get("cache_settings", {}),
        "project_name": final_output_name,
        "output_dir": final_main_out_dir,
        "language": final_gen_text_lang,
        "current_operation_mode": _FLOW_NAME,
        "current_mode_output_options": flow_specific_settings.get("output_options", {}),
        "crawl_url": args.crawl_url,
        "crawl_sitemap": args.crawl_sitemap,
        "crawl_file": crawl_file_final,
        "cli_crawl_depth": crawler_opts_from_resolved_config.get("max_depth_recursive", _FLOW_DEFAULT_MAX_DEPTH_CLI),
        "cli_crawl_output_subdir": crawler_opts_from_resolved_config.get(
            "default_output_subdir_name", _FLOW_DEFAULT_CRAWL_SUBDIR_CLI
        ),
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
    }
    logger.debug("Standalone initial context for %s prepared.", _FLOW_NAME)
    log_llm_in_ctx = initial_context.get("llm_config", {})
    logger.debug(
        "LLM config in final initial_context: %s",
        json.dumps({k: (v if k != "api_key" else "***REDACTED***") for k, v in log_llm_in_ctx.items()}, indent=2),
    )
    return initial_context


def run_standalone_web_crawling() -> None:
    """Run the web crawling and analysis flow independently as a standalone script.

    This function orchestrates the entire process for a standalone run:
    1.  Parses command-line arguments specific to web crawling and analysis.
    2.  Initializes configuration, merging flow defaults, optional global settings,
        and CLI overrides, and sets up logging.
    3.  Prepares the initial shared context required by the web analysis flow.
    4.  Dynamically imports and instantiates the `create_web_crawling_flow`.
    5.  Runs the flow using `run_standalone` from the base `Flow` class.
    6.  Handles potential errors and exceptions during execution.
    7.  Prints a success or failure message to the console.
    """
    args = parse_web_crawling_args()
    resolved_config = _initialize_flow_config_and_logging(args)
    initial_context = _prepare_standalone_initial_context(args, resolved_config)

    logger.info("Starting %s flow (standalone)...", _FLOW_NAME)
    final_flow_settings_for_log = initial_context.get("config", {}).get(_FLOW_NAME, {})
    logger.debug(
        "Effective runtime configuration for flow '%s': %s",
        _FLOW_NAME,
        json.dumps(final_flow_settings_for_log, indent=2, default=str),
    )
    final_common_settings_for_log = initial_context.get("config", {}).get("common", {})
    logger.debug(
        "Effective common settings for flow '%s': %s",
        _FLOW_NAME,
        json.dumps(final_common_settings_for_log, indent=2, default=str),
    )
    final_llm_config_for_log = initial_context.get("llm_config", {})
    logger.debug(
        "Effective LLM config for flow '%s': %s",
        _FLOW_NAME,
        json.dumps(
            {k: (v if k != "api_key" else "***REDACTED***") for k, v in final_llm_config_for_log.items()},
            indent=2,
            default=str,
        ),
    )

    try:
        from .flow import create_web_crawling_flow

        web_pipeline: "SourceLensFlow" = create_web_crawling_flow(initial_context)
        logger.info("Web crawling pipeline created. Running...")
        web_pipeline.run_standalone(initial_context)
        logger.info("Web crawling pipeline finished successfully.")

        final_dir_key = "final_output_dir"
        final_dir_val_any: Any = initial_context.get(final_dir_key) or initial_context.get("final_output_dir_web_crawl")
        final_dir_val: Optional[str] = str(final_dir_val_any) if isinstance(final_dir_val_any, str) else None

        if final_dir_val:
            output_msg_type = "Web summary/tutorial" if initial_context.get(final_dir_key) else "Raw crawled content"
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

    logger.info("%s flow (standalone) finished processing.", _FLOW_NAME)


if __name__ == "__main__":  # pragma: no cover
    run_standalone_web_crawling()

# End of src/FL02_web_crawling/cli.py
