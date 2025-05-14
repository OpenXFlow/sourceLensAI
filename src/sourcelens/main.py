# Copyright (C) 2025 Jozef Darida (Find me on LinkedIn/Xing)
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
initial state preparation, and orchestration of the tutorial generation flow.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from typing_extensions import TypeAlias

# Safe imports for optional dependencies
try:
    import jsonschema

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    JSONSCHEMA_AVAILABLE = False

from sourcelens.config import ConfigError, load_config
from sourcelens.flow import create_tutorial_flow

# Import Flow from the integrated flow engine for type hinting
if TYPE_CHECKING:
    from sourcelens.core.flow_engine_sync import Flow as SourceLensFlow


SharedStateDict: TypeAlias = dict[str, Any]
ConfigDict: TypeAlias = dict[str, Any]

DEFAULT_LOG_DIR_MAIN: str = "logs"


def setup_logging(log_config: dict[str, Any]) -> None:
    """Configure logging based on the loaded configuration."""
    log_dir_str: str = str(log_config.get("log_dir", DEFAULT_LOG_DIR_MAIN))
    log_level_str: str = str(log_config.get("log_level", "INFO")).upper()
    log_level: int = getattr(logging, log_level_str, logging.INFO)
    log_dir: Path = Path(log_dir_str)
    log_file: Optional[Path] = None
    default_log_format: str = "%(asctime)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "sourcelens.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        stream_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(default_log_format)
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        logging.basicConfig(
            level=log_level,
            format=default_log_format,
            handlers=[file_handler, stream_handler],
            force=True,
        )
        logging.getLogger().info("Logging initialized. Log file: %s", log_file)
    except OSError as e:
        print(f"ERROR: Failed create log dir/file '{log_file or log_dir}': {e}", file=sys.stderr)
        logging.basicConfig(
            level=log_level,
            format=default_log_format,
            handlers=[logging.StreamHandler(sys.stdout)],
            force=True,
        )
        logging.getLogger().error("File logging disabled due to setup error.")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the sourceLens tool."""
    parser = argparse.ArgumentParser(
        description="sourceLens: Generate tutorials for codebases using AI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--repo", metavar="REPO_URL", help="URL of the GitHub repository.")
    source_group.add_argument("--dir", metavar="LOCAL_DIR", help="Path to the local directory codebase.")
    parser.add_argument(
        "--config", default="config.json", metavar="FILE_PATH", help="Path to the configuration JSON file."
    )
    parser.add_argument(
        "-n", "--name", metavar="PROJECT_NAME", help="Override project name defined in config or derived from source."
    )
    parser.add_argument(
        "-o", "--output", metavar="OUTPUT_DIR", help="Override the base output directory specified in config."
    )
    parser.add_argument(
        "-i",
        "--include",
        nargs="+",
        metavar="PATTERN",
        help="Override file patterns to include, specified in config language profile.",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        nargs="+",
        metavar="PATTERN",
        help="Override file patterns to exclude, specified in config source section.",
    )
    parser.add_argument(
        "-s",
        "--max-size",
        type=int,
        metavar="BYTES",
        help="Override maximum file size specified in config source section.",
    )
    parser.add_argument("--language", metavar="LANG", help="Override the tutorial output language specified in config.")
    return parser.parse_args()


def _prepare_initial_state(args: argparse.Namespace, config: ConfigDict) -> SharedStateDict:
    """Prepare the initial shared state dictionary based on args and config."""
    source_cfg_any: Any = config.get("source", {})
    output_cfg_any: Any = config.get("output", {})
    project_cfg_any: Any = config.get("project", {})
    github_cfg_any: Any = config.get("github", {})
    llm_cfg_any: Any = config.get("llm", {})
    cache_cfg_any: Any = config.get("cache", {})

    source_cfg: dict[str, Any] = source_cfg_any if isinstance(source_cfg_any, dict) else {}
    output_cfg: dict[str, Any] = output_cfg_any if isinstance(output_cfg_any, dict) else {}
    project_cfg: dict[str, Any] = project_cfg_any if isinstance(project_cfg_any, dict) else {}
    github_cfg: dict[str, Any] = github_cfg_any if isinstance(github_cfg_any, dict) else {}
    llm_cfg: dict[str, Any] = llm_cfg_any if isinstance(llm_cfg_any, dict) else {}
    cache_cfg: dict[str, Any] = cache_cfg_any if isinstance(cache_cfg_any, dict) else {}

    project_name: Optional[str] = args.name or project_cfg.get("default_name")

    include_patterns_raw_any: Any = args.include or source_cfg.get("default_include_patterns", [])
    include_patterns_raw: list[Any] = include_patterns_raw_any if isinstance(include_patterns_raw_any, list) else []
    include_patterns: set[str] = {str(p) for p in include_patterns_raw if isinstance(p, str)}

    exclude_patterns_raw_any: Any = args.exclude or source_cfg.get("default_exclude_patterns", [])
    exclude_patterns_raw: list[Any] = exclude_patterns_raw_any if isinstance(exclude_patterns_raw_any, list) else []
    exclude_patterns: set[str] = {str(p) for p in exclude_patterns_raw if isinstance(p, str)}

    max_size_cfg_any: Any = source_cfg.get("max_file_size_bytes")
    max_size_arg: Optional[int] = (
        args.max_size
        if args.max_size is not None
        else (max_size_cfg_any if isinstance(max_size_cfg_any, int) else None)
    )

    output_dir_cfg_any: Any = output_cfg.get("base_dir", "output")
    output_dir: str = str(args.output or output_dir_cfg_any)

    language_cfg_any: Any = output_cfg.get("language", "english")
    language: str = str(args.language or language_cfg_any)

    local_dir_display_root = ""
    if args.dir:
        local_dir_path = Path(str(args.dir))
        local_dir_display_root = str(local_dir_path.as_posix())
        if local_dir_display_root == ".":
            local_dir_display_root = "./"
        elif not local_dir_display_root.endswith("/"):
            local_dir_display_root += "/"

    initial_state: SharedStateDict = {
        "repo_url": args.repo,
        "local_dir": args.dir,
        "local_dir_display_root": local_dir_display_root,
        "project_name": project_name,
        "config": config,
        "llm_config": llm_cfg,
        "cache_config": cache_cfg,
        "source_config": source_cfg,
        "github_token": github_cfg.get("token"),
        "output_dir": output_dir,
        "language": language,
        "include_patterns": include_patterns,
        "exclude_patterns": exclude_patterns,
        "max_file_size": max_size_arg,
        "use_relative_paths": bool(source_cfg.get("use_relative_paths", True)),
        "files": [],
        "abstractions": [],
        "relationships": {},
        "chapter_order": [],
        "identified_scenarios": [],
        "chapters": [],
        "source_index_content": None,
        "final_output_dir": None,
        "relationship_flowchart_markup": None,
        "class_diagram_markup": None,
        "package_diagram_markup": None,
        "sequence_diagrams_markup": [],
    }
    logging.getLogger(__name__).debug("Initial state prepared. local_dir_display_root: '%s'", local_dir_display_root)
    return initial_state


def _initialize_app(args: argparse.Namespace) -> ConfigDict:
    """Load configuration and set up logging."""
    logger_init = logging.getLogger(__name__)
    config_data: ConfigDict = {}
    validation_exceptions: tuple[type[Exception], ...] = (ConfigError,)
    if (
        JSONSCHEMA_AVAILABLE
        and jsonschema
        and hasattr(jsonschema, "exceptions")
        and hasattr(jsonschema.exceptions, "ValidationError")
    ):
        validation_exceptions += (jsonschema.exceptions.ValidationError,)  # type: ignore[attr-defined]

    try:
        config_path_str = str(args.config)
        config_data = load_config(config_path_str)
        logging_config: dict[str, Any] = (
            config_data.get("logging", {}) if isinstance(config_data.get("logging"), dict) else {}
        )
        setup_logging(logging_config)
        logger_init.info("Config loaded successfully from %s", config_path_str)
        logger_init.debug("Effective LLM Config: %s", config_data.get("llm"))
        logger_init.debug("Effective Source Config: %s", config_data.get("source"))
        logger_init.debug("Effective Output Config: %s", config_data.get("output"))
        return config_data
    except FileNotFoundError as e:
        logging.critical("Configuration file not found: %s", e)
        print(f"\n❌ ERROR: Configuration file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except validation_exceptions as e:  # type: ignore[misc]
        logging.critical("Configuration loading/validation failed: %s", e, exc_info=True)
        print(f"\n❌ ERROR: Configuration loading/validation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        logging.critical("Missing required library for configuration: %s", e)
        print(
            f"\n❌ ERROR: Missing required library for configuration: {e}. Please install dependencies.",
            file=sys.stderr,
        )
        sys.exit(1)
    except OSError as e:
        logging.critical("File system error during config loading: %s", e, exc_info=True)
        print(f"\n❌ ERROR: File system error during config loading: {e}", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, ValueError, KeyError) as e:
        logging.critical("Unexpected error during config processing: %s", e, exc_info=True)
        print(f"\n❌ ERROR: Unexpected error during config processing: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        logging.critical("An unknown critical error occurred during setup: %s", e, exc_info=True)
        print(f"\n❌ CRITICAL ERROR during setup: {e}", file=sys.stderr)
        sys.exit(1)


def _run_flow(initial_state: SharedStateDict) -> None:
    """Create and run the tutorial generation flow."""
    logger_run_flow = logging.getLogger(__name__)
    source_desc_any: Any = initial_state.get("repo_url") or initial_state.get("local_dir")
    source_desc: str = str(source_desc_any) if source_desc_any else "Unknown source"

    logger_run_flow.info("Starting tutorial generation for: %s", source_desc)
    logger_run_flow.info("Output Language: %s", initial_state.get("language"))
    logger_run_flow.info("Output Directory Base: %s", initial_state.get("output_dir"))

    source_config_val_any: Any = initial_state.get("source_config", {})
    source_config_val: dict[str, Any] = source_config_val_any if isinstance(source_config_val_any, dict) else {}
    logger_run_flow.info("Active Source Profile: %s", source_config_val.get("language"))

    llm_cfg_for_log_any: Any = initial_state.get("llm_config", {})
    llm_cfg_for_log: dict[str, Any] = llm_cfg_for_log_any if isinstance(llm_cfg_for_log_any, dict) else {}

    logger_run_flow.info(
        "Active LLM Provider: %s (%s)",
        llm_cfg_for_log.get("provider"),
        "local" if llm_cfg_for_log.get("is_local_llm") else "cloud",
    )
    logger_run_flow.info("Active LLM Model: %s", llm_cfg_for_log.get("model"))

    try:
        llm_config_param_any: Any = initial_state.get("llm_config", {})
        cache_config_param_any: Any = initial_state.get("cache_config", {})

        if not isinstance(llm_config_param_any, dict) or not isinstance(cache_config_param_any, dict):
            raise TypeError("llm_config or cache_config is not a dictionary in shared state.")

        llm_config_param: dict[str, Any] = llm_config_param_any
        cache_config_param: dict[str, Any] = cache_config_param_any

        tutorial_flow: SourceLensFlow = create_tutorial_flow(llm_config_param, cache_config_param)
        tutorial_flow.run(initial_state)

        final_dir_any: Any = initial_state.get("final_output_dir")
        if final_dir_any and isinstance(final_dir_any, str):
            final_dir: str = final_dir_any
            logger_run_flow.info("Tutorial generation completed successfully.")
            print(f"\n✅ Tutorial generation complete! Files are in: {final_dir}")
        else:
            log_msg = "Flow finished, but 'final_output_dir' not set correctly in shared state."
            logger_run_flow.error(log_msg)
            print_msg = "\n⚠️ ERROR: Flow finished, but final output directory was not set."
            print(print_msg, file=sys.stderr)
            sys.exit(1)

    except ImportError as e:
        logging.critical("Failed to import a required module during flow execution: %s", e)
        print(f"\n❌ ERROR: Module import missing or failed during flow: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logging.exception("ERROR: Tutorial generation failed during flow execution.")
        print(f"\n❌ ERROR: Tutorial generation failed: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Run the main entry point for the sourceLens application.

    Parses arguments, initializes the application (config, logging),
    prepares the initial state, and runs the processing flow.
    """
    args: argparse.Namespace = parse_arguments()
    config_data_main: ConfigDict = _initialize_app(args)
    shared_initial_state: SharedStateDict = _prepare_initial_state(args, config_data_main)
    _run_flow(shared_initial_state)


if __name__ == "__main__":
    main()

# End of src/sourcelens/main.py
