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

"""Command-Line Interface for standalone execution of the Code Analysis Flow.

This script allows running the FL01_code_analysis flow independently,
primarily for testing, debugging, or specific use cases where only
code analysis is required. It handles its own argument parsing,
configuration loading (potentially merging with a global config),
logging setup, and execution of the code analysis pipeline.
"""

import argparse
import contextlib
import copy
import importlib
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional, Union, cast
from urllib.parse import urlparse

from typing_extensions import TypeAlias

from sourcelens.config_loader import (
    AUTO_DETECT_OUTPUT_NAME,
    ConfigDict,
    ConfigError,
    ConfigLoader,
)
from sourcelens.utils.helpers import sanitize_filename

if TYPE_CHECKING:  # pragma: no cover
    from sourcelens.core import Flow as SourceLensFlow


logger: logging.Logger = logging.getLogger(__name__)

SharedContextDict: TypeAlias = dict[str, Any]
ResolvedFlowConfigData: TypeAlias = ConfigDict

_FLOW_NAME: Final[str] = "FL01_code_analysis"
_FLOW_DEFAULT_CONFIG_FILENAME: Final[str] = "config.default.json"
_GLOBAL_CONFIG_FILENAME: Final[str] = "config.json"

_FLOW_DEFAULT_LOG_LEVEL: Final[str] = "INFO"
_FLOW_DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s"
_FLOW_DEFAULT_OUTPUT_NAME: Final[str] = "code-analysis-standalone"
_FLOW_DEFAULT_OUTPUT_DIR: Final[str] = f"output_{_FLOW_NAME.lower()}"
_FLOW_DEFAULT_LANGUAGE: Final[str] = "english"
_FLOW_DEFAULT_MAX_FILE_SIZE: Final[int] = 150000
_FLOW_MAX_PROJECT_NAME_LEN: Final[int] = 40


def parse_code_analysis_args() -> argparse.Namespace:
    """Parse command-line arguments specific to the Code Analysis Flow.

    Defines and parses arguments for specifying code source (repository or local
    directory), configuration files, output naming and location, file filtering,
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
    source_group.add_argument("--repo", metavar="REPO_URL", help="URL of the GitHub repository to analyze.")
    source_group.add_argument(
        "--dir", metavar="LOCAL_DIR", type=Path, help="Path to local codebase directory to analyze."
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
    parser.add_argument("-n", "--name", metavar="OUTPUT_NAME", help="Override default output name.")
    parser.add_argument("-o", "--output", metavar="MAIN_OUTPUT_DIR", type=Path, help="Override main output directory.")
    parser.add_argument("-i", "--include", nargs="+", metavar="PATTERN", help="Override include patterns for code.")
    parser.add_argument("-e", "--exclude", nargs="+", metavar="PATTERN", help="Override exclude patterns for code.")
    parser.add_argument("-s", "--max-size", type=int, metavar="BYTES", help="Override max file size for code (bytes).")
    parser.add_argument("--language", metavar="LANG", help="Override generated text language.")
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
        log_config: A dictionary containing logging configuration.
                    Expected keys: 'log_level' (str, e.g., "INFO"),
                    'log_file' (Optional[str], path to log file or "NONE").
    """
    log_level_str: str = str(log_config.get("log_level", _FLOW_DEFAULT_LOG_LEVEL)).upper()
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
        format=_FLOW_DEFAULT_LOG_FORMAT,
        handlers=handlers_to_add,
        force=True,
    )
    logger.info("Logging initialized for %s standalone run at level %s.", _FLOW_NAME, log_level_str)


def _get_local_dir_display_root_cli(local_dir_str: Optional[str]) -> str:
    """Return the display root for local directories for CLI output or context.

    Normalizes the path, ensuring it ends with a slash if it's not empty
    and handles the "." case to be "./".

    Args:
        local_dir_str: The path string to the local directory, possibly relative.

    Returns:
        str: A normalized string representation of the local directory root,
             suitable for display or as a base for relative paths.
             Returns an empty string if `local_dir_str` is None or empty.
    """
    if not local_dir_str or not isinstance(local_dir_str, str):
        return ""
    display_root_str: str = ""
    with contextlib.suppress(ValueError, TypeError, OSError):
        path_obj = Path(local_dir_str)
        if path_obj:
            display_root_str = path_obj.as_posix()
            if display_root_str == ".":
                display_root_str = "./"
            elif display_root_str and not display_root_str.endswith("/"):
                display_root_str += "/"
    return display_root_str


def _derive_name_from_code_source_cli(args: argparse.Namespace) -> str:
    """Derive an output name for code sources based on repository URL or local directory.

    Prioritizes repository URL if available, then local directory name.
    The derived name is sanitized for use in filenames.

    Args:
        args: Parsed command-line arguments from `argparse.ArgumentParser`.
              Expected to have `repo` (Optional[str]) and `dir` (Optional[Path]) attributes.

    Returns:
        str: A sanitized, derived name suitable for output identification.
             Returns a default name if derivation fails.
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
        sanitize_filename(name_candidate, max_len=_FLOW_MAX_PROJECT_NAME_LEN)
        if name_candidate
        else _FLOW_DEFAULT_OUTPUT_NAME
    )


def _derive_name_if_auto_cli(args: argparse.Namespace, current_name: str) -> str:
    """Derive output name if the current name indicates auto-detection.

    If `current_name` is the `AUTO_DETECT_OUTPUT_NAME` sentinel, this function
    attempts to derive a name from the source (CLI's --repo or --dir).
    If the user provided a --name via CLI, that takes precedence over auto-derivation.

    Args:
        args: Parsed command-line arguments.
        current_name: The current output name, typically from configuration.

    Returns:
        str: The final output name. If `current_name` is not `AUTO_DETECT_OUTPUT_NAME`,
             it's returned directly. Otherwise, a derived or CLI-provided name is returned.
    """
    if current_name != AUTO_DETECT_OUTPUT_NAME:
        return current_name
    if args.name:
        return str(args.name)
    derived = _derive_name_from_code_source_cli(args)
    return derived or _FLOW_DEFAULT_OUTPUT_NAME


class DummyConfigLoaderForFlowCLI:
    """A simplified configuration loader for standalone flow CLI execution.

    This loader is used when a global SourceLens configuration file is not
    provided or found. It loads the flow's default configuration and merges
    it with a minimal global structure (if any global config was loadable)
    and applies basic CLI argument overrides. It does not perform full LLM
    profile resolution from environment variables like the main `ConfigLoader`.
    """

    _global_config_data: ConfigDict
    _logger_dummy: logging.Logger

    def __init__(self, global_config_path_str: Optional[str] = None) -> None:
        """Initialize the DummyConfigLoader.

        Tries to load a global configuration if `global_config_path_str` is provided.
        If not, or if loading fails, it uses a minimal internal global configuration
        structure (empty common and profiles).

        Args:
            global_config_path_str: Optional path to a global configuration file.
        """
        self._logger_dummy = logging.getLogger(self.__class__.__name__)
        self._global_config_data = {"common": {}, "profiles": {}}
        if global_config_path_str:
            try:
                global_path = Path(global_config_path_str).resolve(strict=True)
                self._global_config_data = self._read_json_file(global_path)
                self._logger_dummy.info("DummyLoader: Successfully loaded global config from %s", global_path)
            except (FileNotFoundError, ConfigError) as e_load_global:
                log_msg_part1 = f"DummyLoader: Could not load global config from '{global_config_path_str}': "
                log_msg_part2 = f"{e_load_global}. Using minimal global."
                self._logger_dummy.warning(log_msg_part1 + log_msg_part2)
        else:
            self._logger_dummy.info("DummyLoader: No global config path provided. Using minimal global structure.")

    def _read_json_file(self, fp: Path) -> ConfigDict:
        """Read and parse a JSON configuration file.

        Args:
            fp: Path object pointing to the JSON file.

        Returns:
            ConfigDict: The loaded configuration as a dictionary.

        Raises:
            ConfigError: If the file cannot be read, is not valid JSON,
                         or the root JSON structure is not a dictionary.
            TypeError: If the loaded data is not a dictionary (internal check).
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
        """Deeply merge the `override` dictionary into the `base` dictionary.

        Modifies the `base` dictionary in-place. If a key exists in both and
        both values are dictionaries, it recursively merges them. Otherwise,
        the value from `override` replaces the value in `base`.

        Args:
            base: The base configuration dictionary (modified in-place).
            override: The dictionary whose values will override those in `base`.

        Returns:
            ConfigDict: The modified `base` dictionary.
        """
        for k, v_override in override.items():
            if isinstance(v_override, dict) and isinstance(base.get(k), dict):
                self._deep_merge_configs(base[k], v_override)  # type: ignore[arg-type]
            else:
                base[k] = v_override
        return base

    def _apply_simplified_cli_overrides(self, cfg: ConfigDict, cli_args: argparse.Namespace, flow_nm: str) -> None:  # noqa: C901
        """Apply a simplified set of CLI overrides for the dummy loader.

        This is a less complex version than in the main `ConfigLoader`. It handles
        common overrides and some flow-specific ones for code analysis.

        Args:
            cfg: The configuration dictionary to modify.
            cli_args: Parsed command-line arguments.
            flow_nm: The name of the current flow (e.g., "FL01_code_analysis").
        """
        self._logger_dummy.debug("DummyLoader applying simplified CLI args to config.")
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
            source_opts = flow_block.setdefault("source_options", {})
            if getattr(cli_args, "include", None):
                source_opts["include_patterns"] = cli_args.include
            if getattr(cli_args, "exclude", None):
                source_opts["default_exclude_patterns"] = cli_args.exclude
            if getattr(cli_args, "max_size", None) is not None:
                source_opts["max_file_size_bytes"] = cli_args.max_size
            if getattr(cli_args, "llm_provider", None):
                flow_block["active_llm_provider_id"] = cli_args.llm_provider

    def get_resolved_flow_config(
        self,
        flow_name: str,
        flow_default_config_path: Path,
        cli_args: Optional[argparse.Namespace] = None,
    ) -> ResolvedFlowConfigData:
        """Get resolved configuration for the flow for standalone CLI execution.

        Merges the flow's default configuration, (optional) global common/profiles,
        and CLI arguments. Does not perform full environment variable resolution
        for API keys like the main `ConfigLoader`.

        Args:
            flow_name: The name of the flow (e.g., "FL01_code_analysis").
            flow_default_config_path: Path to the flow's default `config.default.json`.
            cli_args: Optional parsed command-line arguments namespace.

        Returns:
            ResolvedFlowConfigData: The merged and partially resolved configuration.
        """
        self._logger_dummy.info("DummyLoader resolving config for flow: %s", flow_name)
        default_cfg = self._read_json_file(flow_default_config_path)
        merged_cfg = copy.deepcopy(default_cfg)

        self._deep_merge_configs(merged_cfg.setdefault("common", {}), self._global_config_data.get("common", {}))
        merged_cfg.setdefault("profiles", {}).update(self._global_config_data.get("profiles", {}))

        global_flow_overrides = self._global_config_data.get(flow_name, {})
        if global_flow_overrides:
            merged_cfg_flow_block = merged_cfg.setdefault(flow_name, {})
            self._deep_merge_configs(merged_cfg_flow_block, global_flow_overrides)

        if cli_args:
            self._apply_simplified_cli_overrides(merged_cfg, cli_args, flow_name)

        llm_default_opts = merged_cfg.get("common", {}).get("llm_default_options", {})
        flow_settings_block = merged_cfg.get(flow_name, {})
        active_llm_id = (
            flow_settings_block.get("active_llm_provider_id") if isinstance(flow_settings_block, dict) else None
        )

        profiles = merged_cfg.get("profiles", {}).get("llm_profiles", [])
        resolved_llm_cfg = copy.deepcopy(llm_default_opts)

        if active_llm_id and isinstance(active_llm_id, str) and isinstance(profiles, list):
            active_profile = next(
                (p for p in profiles if isinstance(p, dict) and p.get("provider_id") == active_llm_id), None
            )
            if active_profile:
                resolved_llm_cfg.update(active_profile)

        if cli_args:
            if getattr(cli_args, "llm_model", None):
                resolved_llm_cfg["model"] = cli_args.llm_model
            if getattr(cli_args, "api_key", None):
                resolved_llm_cfg["api_key"] = cli_args.api_key

        merged_cfg["resolved_llm_config"] = resolved_llm_cfg

        if flow_name == _FLOW_NAME:
            flow_block_final = merged_cfg.get(_FLOW_NAME, {})
            if isinstance(flow_block_final, dict):
                flow_block_final.setdefault("resolved_github_token", flow_block_final.get("github_token"))

        return cast(ResolvedFlowConfigData, merged_cfg)


def _initialize_flow_config_and_logging_logic(args: argparse.Namespace) -> ResolvedFlowConfigData:
    """Core logic for initializing configuration and logging for standalone flow.

    Determines paths, chooses loader (real or dummy), resolves configuration by
    merging flow default, global (if any), and CLI arguments.

    Args:
        args: Parsed command-line arguments from `argparse.ArgumentParser`.

    Returns:
        ResolvedFlowConfigData: The fully resolved configuration for the flow.

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
        for _ in range(3):
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
            logger.warning("No global config. Using DummyConfigLoader with flow defaults and minimal global.")
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
    """Initialize ConfigLoader, resolve config for this flow, and set up logging.

    This function acts as a wrapper around `_initialize_flow_config_and_logging_logic`
    to provide centralized error handling for configuration and logging setup.

    Args:
        args: Parsed command-line arguments.

    Returns:
        ResolvedFlowConfigData: The fully resolved configuration for this flow.

    Raises:
        SystemExit: If configuration or logging setup fails critically.
    """
    try:
        return _initialize_flow_config_and_logging_logic(args)
    except (ConfigError, FileNotFoundError, ValueError, TypeError, AttributeError) as e_conf:
        print(f"ERROR: {_FLOW_NAME} CLI - Configuration setup failed: {e_conf!s}", file=sys.stderr)
        if not logger.handlers:
            logging.basicConfig(level=logging.ERROR, format=_FLOW_DEFAULT_LOG_FORMAT, stream=sys.stderr)
        logger.critical("Configuration error: %s", e_conf, exc_info=True)
        sys.exit(1)
    except (ImportError, RuntimeError, OSError) as e_unexpected:  # pragma: no cover
        print(f"ERROR: {_FLOW_NAME} CLI - Unexpected error during init: {e_unexpected!s}", file=sys.stderr)
        if not logger.handlers:
            logging.basicConfig(level=logging.ERROR, format=_FLOW_DEFAULT_LOG_FORMAT, stream=sys.stderr)
        logger.critical("Unexpected initialization error: %s", e_unexpected, exc_info=True)
        sys.exit(1)


def _prepare_standalone_initial_context(
    args: argparse.Namespace, resolved_flow_config: ResolvedFlowConfigData
) -> SharedContextDict:
    """Prepare the initial shared context for a standalone code analysis run.

    This function populates the `initial_context` dictionary with values derived
    from parsed command-line arguments and the fully resolved flow configuration.
    It sets up all necessary keys that the code analysis flow and its nodes expect.

    Args:
        args: Parsed command-line arguments.
        resolved_flow_config: The fully resolved configuration specific to this
                              code analysis flow, after merging defaults, global
                              settings, and CLI overrides.

    Returns:
        SharedContextDict: The initial context dictionary ready for the pipeline.
    """
    common_settings: dict[str, Any] = resolved_flow_config.get("common", {})
    common_output_settings: dict[str, Any] = common_settings.get("common_output_settings", {})
    flow_specific_settings: dict[str, Any] = resolved_flow_config.get(_FLOW_NAME, {})

    output_name_from_config = str(common_output_settings.get("default_output_name", AUTO_DETECT_OUTPUT_NAME))
    final_output_name = _derive_name_if_auto_cli(args, output_name_from_config)

    main_out_dir_from_config = str(common_output_settings.get("main_output_directory", _FLOW_DEFAULT_OUTPUT_DIR))
    final_main_out_dir = str(args.output) if args.output else main_out_dir_from_config

    gen_text_lang_from_config = str(common_output_settings.get("generated_text_language", _FLOW_DEFAULT_LANGUAGE))
    final_gen_text_lang = str(args.language) if args.language else gen_text_lang_from_config

    source_opts_from_config = flow_specific_settings.get("source_options", {})
    include_patterns = set(source_opts_from_config.get("include_patterns", []))
    exclude_patterns = set(source_opts_from_config.get("default_exclude_patterns", []))
    max_file_size = int(source_opts_from_config.get("max_file_size_bytes", _FLOW_DEFAULT_MAX_FILE_SIZE))

    initial_context: SharedContextDict = {
        "config": resolved_flow_config,
        "llm_config": resolved_flow_config.get("resolved_llm_config", {}),
        "cache_config": common_settings.get("cache_settings", {}),
        "project_name": final_output_name,
        "output_dir": final_main_out_dir,
        "language": final_gen_text_lang,
        "current_operation_mode": _FLOW_NAME,  # Use internal flow name
        "current_mode_output_options": flow_specific_settings.get("output_options", {}),
        "repo_url": args.repo,
        "local_dir": str(args.dir) if args.dir else None,
        "source_config": flow_specific_settings.get("source_config", {}),
        "github_token": flow_specific_settings.get("resolved_github_token"),
        "include_patterns": include_patterns,
        "exclude_patterns": exclude_patterns,
        "max_file_size": max_file_size,
        "use_relative_paths": bool(source_opts_from_config.get("use_relative_paths", True)),
        "local_dir_display_root": _get_local_dir_display_root_cli(str(args.dir) if args.dir else None),
        "files": [],
        "abstractions": [],
        "relationships": {},
        "chapter_order": [],
        "identified_scenarios": [],
        "chapters": [],
        "source_index_content": None,
        "project_review_content": None,
        "final_output_dir": None,
        "relationship_flowchart_markup": None,
        "class_diagram_markup": None,
        "package_diagram_markup": None,
        "file_structure_diagram_markup": None,
        "sequence_diagrams_markup": [],
    }
    logger.debug("Standalone initial context for %s prepared.", _FLOW_NAME)
    return initial_context


def run_standalone_code_analysis() -> None:
    """Run the code analysis flow independently as a standalone script.

    This function orchestrates the entire process for a standalone run:
    1.  Parses command-line arguments specific to code analysis.
    2.  Initializes configuration, merging flow defaults, optional global settings,
        and CLI overrides, and sets up logging.
    3.  Prepares the initial shared context required by the flow.
    4.  Dynamically imports and instantiates the `create_code_analysis_flow`.
    5.  Runs the flow using `run_standalone` from the base `Flow` class.
    6.  Handles potential errors and exceptions during execution.
    7.  Prints a success or failure message to the console.
    """
    args = parse_code_analysis_args()
    resolved_config = _initialize_flow_config_and_logging(args)
    initial_context = _prepare_standalone_initial_context(args, resolved_config)

    logger.info("Starting %s flow (standalone)...", _FLOW_NAME)
    # Log the specific flow config being used, not the entire resolved_config
    # which might contain other flow data if a global config was used.
    flow_config_for_run = initial_context.get("config", {}).get(_FLOW_NAME, {})
    logger.debug("Effective runtime configuration for flow: %s", flow_config_for_run)
    logger.debug("Effective common settings for flow: %s", initial_context.get("config", {}).get("common"))
    logger.debug("Effective LLM config for flow: %s", initial_context.get("llm_config"))

    try:
        # Construct the full module path relative to the 'src' directory or top-level package
        # If FL01_code_analysis is a top-level package:
        # from FL01_code_analysis.flow import create_code_analysis_flow
        # If it's under 'src':
        flow_module = importlib.import_module(f"src.{_FLOW_NAME}.flow")
        create_code_analysis_flow_func = getattr(flow_module, "create_code_analysis_flow")

        code_pipeline: "SourceLensFlow" = create_code_analysis_flow_func(initial_context)
        logger.info("Code analysis pipeline created. Running...")
        code_pipeline.run_standalone(initial_context)
        logger.info("Code analysis pipeline finished successfully.")
        final_dir_val_any: Any = initial_context.get("final_output_dir")
        final_dir_val: Optional[str] = str(final_dir_val_any) if isinstance(final_dir_val_any, str) else None

        if final_dir_val:
            print(f"\n✅ Standalone code analysis complete! Output in: {Path(final_dir_val).resolve()}")
        else:  # pragma: no cover
            print("\n⚠️ Standalone code analysis finished, but no output directory was set in context.")

    except (ConfigError, ValueError, TypeError, AttributeError, RuntimeError, OSError, ImportError) as e_flow:
        no_files_error_type: Optional[type[Exception]] = None
        try:
            nff_module = importlib.import_module(f"src.{_FLOW_NAME}.nodes.n01_fetch_code")
            no_files_error_type = getattr(nff_module, "NoFilesFetchedError", None)
        except ImportError:  # pragma: no cover
            logger.warning("Could not dynamically import NoFilesFetchedError for specific handling.")

        if no_files_error_type and isinstance(e_flow, cast(type, no_files_error_type)):
            logger.error("No files fetched during standalone code analysis: %s", e_flow, exc_info=False)
            print(f"\n❌ ERROR: No source files were found for analysis. Details: {e_flow}", file=sys.stderr)
            sys.exit(1)
        else:  # pragma: no cover
            logger.critical("Error during standalone code analysis pipeline execution: %s", e_flow, exc_info=True)
            print(f"\n❌ ERROR: Pipeline execution failed: {e_flow!s}", file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:  # pragma: no cover
        logger.warning("Standalone code analysis execution interrupted by user.")
        print("\n❌ Execution interrupted by user.", file=sys.stderr)
        sys.exit(130)

    logger.info("%s flow (standalone) finished processing.", _FLOW_NAME)


if __name__ == "__main__":  # pragma: no cover
    # Ensure the 'src' directory is in sys.path if running this script directly
    # for standalone testing, and 'src' is the parent of FL01_code_analysis package.
    # This helps with relative imports like 'from .flow import ...'
    # or 'from ..utils import ...' if nodes were to use them.
    current_script_path = Path(__file__).resolve()  # C:\...\src\FL01_code_analysis\cli.py
    project_src_root = current_script_path.parent.parent  # C:\...\src
    if str(project_src_root) not in sys.path:
        sys.path.insert(0, str(project_src_root))
        logger.debug("Added '%s' to sys.path for standalone CLI execution.", project_src_root)

    run_standalone_code_analysis()

# End of src/FL01_code_analysis/cli.py
