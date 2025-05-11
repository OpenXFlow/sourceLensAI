# src/sourcelens/main.py

"""Command-line interface entry point for the sourceLens application.

Handles argument parsing, configuration loading, logging setup,
initial state preparation, and orchestration of the tutorial generation flow.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, TypeAlias  # Removed Type

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
    from sourcelens.core.flow_engine import Flow as SourceLensFlow


SharedStateDict: TypeAlias = dict[str, Any]
ConfigDict: TypeAlias = dict[str, Any]

DEFAULT_LOG_DIR_MAIN: str = "logs"


def setup_logging(log_config: dict[str, Any]) -> None:
    """Configure logging based on the loaded configuration."""
    log_dir_str = log_config.get("log_dir", DEFAULT_LOG_DIR_MAIN)
    log_level_str = log_config.get("log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_dir = Path(log_dir_str)
    log_file: Optional[Path] = None
    log_format = "%(asctime)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "sourcelens.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        stream_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(log_format)
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[file_handler, stream_handler],
            force=True,
        )
        logging.getLogger().info("Logging initialized. Log file: %s", log_file)
    except OSError as e:
        print(f"ERROR: Failed create log dir/file '{log_file or log_dir}': {e}", file=sys.stderr)
        logging.basicConfig(
            level=log_level,
            format=log_format,
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
    source_cfg = config.get("source", {})
    output_cfg = config.get("output", {})
    project_cfg = config.get("project", {})
    github_cfg = config.get("github", {})
    llm_cfg = config.get("llm", {})
    cache_cfg = config.get("cache", {})
    project_name: Optional[str] = args.name or project_cfg.get("default_name")

    include_patterns_raw = args.include or source_cfg.get("default_include_patterns", [])
    include_patterns: set[str] = {str(p) for p in include_patterns_raw} if include_patterns_raw else set()

    exclude_patterns_raw = args.exclude or source_cfg.get("default_exclude_patterns", [])
    exclude_patterns: set[str] = {str(p) for p in exclude_patterns_raw} if exclude_patterns_raw else set()

    max_size_arg = args.max_size if args.max_size is not None else source_cfg.get("max_file_size_bytes")
    output_dir: str = str(args.output or output_cfg.get("base_dir", "output"))
    language: str = str(args.language or output_cfg.get("language", "english"))

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
        "use_relative_paths": source_cfg.get("use_relative_paths", True),
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
    validation_exceptions: tuple[type[Exception], ...] = (ConfigError,)  # Use built-in type
    if JSONSCHEMA_AVAILABLE and jsonschema and hasattr(jsonschema, "exceptions"):
        validation_exceptions += (jsonschema.exceptions.ValidationError,)  # type: ignore[attr-defined]
    try:
        config_path_str = str(args.config)
        config_data = load_config(config_path_str)
        setup_logging(config_data.get("logging", {}))
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
        logging.critical("Missing required library: %s", e)
        print(f"\n❌ ERROR: Missing required library: {e}. Please install dependencies.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        logging.critical("File system error during setup: %s", e, exc_info=True)
        print(f"\n❌ ERROR: File system error during setup: {e}", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, ValueError, KeyError) as e:
        logging.critical("Unexpected error during setup: %s", e, exc_info=True)
        print(f"\n❌ ERROR: Unexpected error during setup: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        logging.critical("An unknown critical error occurred during setup: %s", e, exc_info=True)
        print(f"\n❌ CRITICAL ERROR during setup: {e}", file=sys.stderr)
        sys.exit(1)


def _run_flow(initial_state: SharedStateDict) -> None:
    """Create and run the tutorial generation flow."""
    logger_run_flow = logging.getLogger(__name__)
    source_desc = initial_state.get("repo_url") or initial_state.get("local_dir")
    logger_run_flow.info("Starting tutorial generation for: %s", source_desc)
    logger_run_flow.info("Output Language: %s", initial_state.get("language"))
    logger_run_flow.info("Output Directory Base: %s", initial_state.get("output_dir"))
    logger_run_flow.info("Active Source Profile: %s", initial_state.get("source_config", {}).get("language"))
    llm_cfg_for_log = initial_state.get("llm_config", {})
    logger_run_flow.info(
        "Active LLM Provider: %s (%s)",
        llm_cfg_for_log.get("provider"),
        "local" if llm_cfg_for_log.get("is_local_llm") else "cloud",
    )
    logger_run_flow.info("Active LLM Model: %s", llm_cfg_for_log.get("model"))

    try:
        llm_config_param = initial_state.get("llm_config", {})
        cache_config_param = initial_state.get("cache_config", {})
        if not isinstance(llm_config_param, dict) or not isinstance(cache_config_param, dict):
            raise TypeError("llm_config or cache_config is not a dictionary.")

        tutorial_flow: SourceLensFlow = create_tutorial_flow(llm_config_param, cache_config_param)
        tutorial_flow.run(initial_state)

        final_dir = initial_state.get("final_output_dir")
        if final_dir and isinstance(final_dir, str):
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
    except Exception as e:  # noqa: BLE001
        logging.exception("ERROR: Tutorial generation failed during flow execution.")
        print(f"\n❌ ERROR: Tutorial generation failed: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Run the main entry point for the sourceLens application.

    Parses arguments, initializes the application (config, logging),
    prepares the initial state, and runs the processing flow.
    """
    args = parse_arguments()
    config_data_main = _initialize_app(args)
    shared_initial_state = _prepare_initial_state(args, config_data_main)
    _run_flow(shared_initial_state)


if __name__ == "__main__":
    main()

# End of src/sourcelens/main.py
