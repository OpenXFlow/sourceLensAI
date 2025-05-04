# src/sourcelens/main.py

"""Command-line interface entry point for the sourceLens application.

Handles argument parsing, configuration loading, logging setup,
initial state preparation, and orchestration of the tutorial generation flow.
"""

import argparse
import logging
import sys
from pathlib import Path

# Using modern types directly
from typing import TYPE_CHECKING, Any, Optional, TypeAlias

import jsonschema  # Keep import for exception handling

from sourcelens.config import ConfigError, load_config
from sourcelens.flow import create_tutorial_flow

# Use TYPE_CHECKING block for imports needed only for type hints
if TYPE_CHECKING:
    from pocketflow import Flow
    # ConfigDict defined below

# Type Alias definitions
SharedStateDict: TypeAlias = dict[str, Any]
ConfigDict: TypeAlias = dict[str, Any]

# Constants from config
try:
    from sourcelens.config import DEFAULT_LOG_DIR
except ImportError:
    DEFAULT_LOG_DIR = "logs"


def setup_logging(log_config: dict[str, Any]) -> None:
    """Configure logging based on the loaded configuration."""
    # --- Implementation remains the same ---
    log_dir_str = log_config.get("log_dir", DEFAULT_LOG_DIR)
    log_level_str = log_config.get("log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_dir = Path(log_dir_str)
    log_file: Optional[Path] = None
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "sourcelens.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        stream_handler = logging.StreamHandler(sys.stdout)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[file_handler, stream_handler],
            force=True,
        )
        logging.info("Logging initialized. Log file: %s", log_file)
    except OSError as e:
        print(f"ERROR: Failed create log dir/file '{log_file or log_dir}': {e}", file=sys.stderr)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
            force=True,
        )
        logging.error("File logging disabled due to setup error.")
    # --- End of unchanged setup_logging ---


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the sourceLens tool."""
    # --- Implementation remains the same ---
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
    parser.add_argument("-n", "--name", metavar="PROJECT_NAME", help="Override project name.")
    parser.add_argument("-o", "--output", metavar="OUTPUT_DIR", help="Override the base output directory.")
    parser.add_argument("-i", "--include", nargs="+", metavar="PATTERN", help="Override include file patterns.")
    parser.add_argument("-e", "--exclude", nargs="+", metavar="PATTERN", help="Override exclude file patterns.")
    parser.add_argument("-s", "--max-size", type=int, metavar="BYTES", help="Override maximum file size.")
    parser.add_argument("--language", metavar="LANG", help="Override the tutorial language.")
    return parser.parse_args()
    # --- End of unchanged parse_arguments ---


def _prepare_initial_state(args: argparse.Namespace, config: ConfigDict) -> SharedStateDict:
    """Prepare the initial shared state dictionary based on args and config."""
    # Config sections already processed by load_config
    source_cfg = config.get("source", {})
    output_cfg = config.get("output", {})
    project_cfg = config.get("project", {})
    github_cfg = config.get("github", {})
    llm_cfg = config.get("llm", {})
    cache_cfg = config.get("cache", {})

    # Override values from args
    project_name: Optional[str] = args.name or project_cfg.get("default_name")
    include_patterns: set[str] = set(args.include or source_cfg.get("default_include_patterns", []))
    exclude_patterns: set[str] = set(args.exclude or source_cfg.get("default_exclude_patterns", []))
    max_size: int = args.max_size if args.max_size is not None else source_cfg.get("max_file_size_bytes")
    output_dir: str = args.output or output_cfg.get("base_dir")
    language: str = args.language or output_cfg.get("language")

    # --- Prepare the state dictionary ---
    initial_state: SharedStateDict = {
        # Input parameters
        "repo_url": args.repo,
        "local_dir": args.dir,
        "project_name": project_name,
        # Pass entire processed config + specific subsets for convenience
        "config": config,
        "llm_config": llm_cfg,
        "cache_config": cache_cfg,
        "source_config": source_cfg,
        "github_token": github_cfg.get("token"),
        # Settings used directly by nodes
        "output_dir": output_dir,
        "language": language,
        "include_patterns": include_patterns,
        "exclude_patterns": exclude_patterns,
        "max_file_size": max_size,
        "use_relative_paths": source_cfg.get("use_relative_paths", True),
        # Initial empty states for pipeline data
        "files": [],
        "abstractions": [],
        "relationships": {},
        "chapter_order": [],
        "chapters": [],
        "final_output_dir": None,
        # --- Initialize placeholders for diagram results ---
        "relationship_flowchart_markup": None,
        "class_diagram_markup": None,
        "package_diagram_markup": None,
        "sequence_diagrams_markup": [],
    }
    return initial_state


def main() -> None:  # noqa: PLR0915, C901 - Keep main logic together for clarity
    """Run the main entry point for the sourceLens application."""
    args = parse_arguments()
    config: ConfigDict = {}
    try:
        config_path_str = args.config
        config = load_config(config_path_str)
        setup_logging(config.get("logging", {}))
        logging.info("Config loaded successfully from %s", config_path_str)
        logging.debug("Effective LLM Config: %s", config.get("llm"))
        logging.debug("Effective Source Config: %s", config.get("source"))
        logging.debug("Effective Output Config: %s", config.get("output"))
    # --- Refined Exception Handling ---
    except FileNotFoundError as e:
        logging.critical("Configuration file not found: %s", e)
        print(f"\n❌ ERROR: Configuration file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except (ConfigError, jsonschema.exceptions.ValidationError) as e:
        logging.critical("Configuration loading/validation failed: %s", e, exc_info=True)
        print(f"\n❌ ERROR: Configuration loading/validation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        logging.critical("Missing required library: %s", e)
        print(f"\n❌ ERROR: Missing required library: {e}. Install dependencies.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        logging.critical("File system error during setup: %s", e, exc_info=True)
        print(f"\n❌ ERROR: File system error during setup: {e}", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, ValueError, KeyError) as e:  # Catch specific unexpected setup errors
        logging.critical("Unexpected error during setup: %s", e, exc_info=True)
        print(f"\n❌ ERROR: Unexpected error during setup: {e}", file=sys.stderr)
        sys.exit(1)
    # --- End Refined Exception Handling ---

    shared_initial_state = _prepare_initial_state(args, config)

    source_desc = shared_initial_state["repo_url"] or shared_initial_state["local_dir"]
    logging.info("Starting tutorial generation for: %s", source_desc)
    logging.info("Output Language: %s", shared_initial_state["language"])
    logging.info("Output Directory Base: %s", shared_initial_state["output_dir"])
    logging.info("Active Source Profile: %s", shared_initial_state.get("source_config", {}).get("language"))
    logging.info(
        "Active LLM Provider: %s (%s)",
        shared_initial_state.get("llm_config", {}).get("provider"),
        "local" if shared_initial_state.get("llm_config", {}).get("is_local_llm") else "cloud",
    )
    logging.info("Active LLM Model: %s", shared_initial_state.get("llm_config", {}).get("model"))

    try:
        tutorial_flow: Flow = create_tutorial_flow(
            shared_initial_state["llm_config"], shared_initial_state["cache_config"]
        )
        # PocketFlow run modifies shared state in place
        tutorial_flow.run(shared_initial_state)

        final_dir = shared_initial_state.get("final_output_dir")
        if final_dir and isinstance(final_dir, str):
            logging.info("Tutorial generation completed successfully.")
            print(f"\n✅ Tutorial generation complete! Files are in: {final_dir}")
        else:
            log_msg = "Flow finished, but 'final_output_dir' not set correctly."
            logging.error(log_msg)
            print_msg = "\n⚠️ ERROR: Flow finished, but final output directory was not set."
            print(print_msg, file=sys.stderr)
            sys.exit(1)

    except ImportError as e:  # e.g., PocketFlow missing
        logging.critical("Failed import or use PocketFlow: %s", e)
        print(f"\n❌ ERROR: Core dependency PocketFlow missing/failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # Catch any other unhandled errors during flow
        # Log the full traceback for flow execution errors
        logging.exception("ERROR: Tutorial generation failed during flow execution.")
        print(f"\n❌ ERROR: Tutorial generation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

# End of src/sourcelens/main.py
