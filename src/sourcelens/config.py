# src/sourcelens/config.py

"""Configuration loading, validation, and processing for the SourceLens application.

Handles reading settings from a JSON file, validating the structure against a
defined JSON schema, resolving secrets from environment variables, selecting
active LLM and language profiles, applying default values, and ensuring necessary
directories (cache, logs) exist. Provides a single, validated configuration
dictionary for the application. Includes detailed schema definitions for all
configurable sections, including diagram generation options.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional, TypeAlias

# Safe imports for optional dependencies
try:
    import jsonschema
    from jsonschema import validate

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    validate = None  # type: ignore[assignment]
    JSONSCHEMA_AVAILABLE = False


# --- Type Aliases ---
ConfigDict: TypeAlias = dict[str, Any]
ProviderConfigDict: TypeAlias = dict[str, Any]
LanguageProfileDict: TypeAlias = dict[str, Any]

# --- Constants ---
DEFAULT_CACHE_FILE = ".cache/llm_cache.json"
DEFAULT_LOG_DIR = "logs"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_LANGUAGE = "english"
DEFAULT_MAX_FILE_SIZE = 150000
DEFAULT_LLM_RETRIES = 3
DEFAULT_LLM_WAIT = 10
# Environment variable names
ENV_VAR_GOOGLE_PROJECT = "GOOGLE_CLOUD_PROJECT"
ENV_VAR_GOOGLE_REGION = "GOOGLE_CLOUD_REGION"
ENV_VAR_GITHUB_TOKEN = "GITHUB_TOKEN"
ENV_VAR_GEMINI_KEY = "GEMINI_API_KEY"
ENV_VAR_VERTEX_CREDS = "GOOGLE_APPLICATION_CREDENTIALS"
ENV_VAR_ANTHROPIC_KEY = "ANTHROPIC_API_KEY"
ENV_VAR_OPENAI_KEY = "OPENAI_API_KEY"
ENV_VAR_PERPLEXITY_KEY = "PERPLEXITY_API_KEY"


# --- JSON Schema Definitions ---

LLM_PROVIDER_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "is_active": {"type": "boolean", "description": "Whether this provider configuration is currently active."},
        "is_local_llm": {"type": "boolean", "description": "True if this provider uses a locally hosted LLM."},
        "provider": {"type": "string", "description": "Identifier for the LLM provider."},
        "model": {"type": "string", "description": "Specific model name for the provider."},
        "api_key": {"type": ["string", "null"], "description": "API key. If null, loads from env vars."},
        "api_base_url": {
            "type": ["string", "null"],
            "description": "Base URL for API endpoint (for local/compatible).",
        },
        "vertex_project": {"type": ["string", "null"], "description": "GCP Project ID for Vertex AI."},
        "vertex_location": {"type": ["string", "null"], "description": "GCP Region for Vertex AI."},
    },
    "required": ["is_active", "is_local_llm", "provider", "model"],
    "additionalProperties": False,
}

LANGUAGE_PROFILE_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "is_active": {"type": "boolean", "description": "Whether this language profile is currently active."},
        "language": {"type": "string", "description": "Identifier for the language."},
        "default_include_patterns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of glob patterns for files to include.",
            "default": [],
        },
        "max_file_size_bytes": {
            "type": ["integer", "null"],
            "minimum": 0,
            "description": "Optional language-specific override for max file size.",
            "default": None,
        },
        "use_relative_paths": {
            "type": ["boolean", "null"],
            "description": "Optional language-specific override for using relative paths.",
            "default": None,
        },
    },
    "required": ["is_active", "language"],
    "additionalProperties": False,
}

# --- Schema for Sequence Diagram config (REVISED - no scenarios list) ---
SEQUENCE_DIAGRAM_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {
            "type": "boolean",
            "default": False,
            "description": "Whether to generate sequence diagrams for dynamically identified scenarios.",
        },
        "max_diagrams": {
            "type": "integer",
            "minimum": 1,
            "default": 5,
            "description": "Max number of sequence diagrams to generate from identified scenarios.",
        },
        # "scenarios" list removed
    },
    "additionalProperties": False,
    "default": {"enabled": False, "max_diagrams": 5},
}

# --- Schema for Diagram Generation (REVISED - no separate_markup_file_generated) ---
DIAGRAM_GENERATION_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        # "separate_markup_file_generated" removed
        "format": {
            "type": "string",
            "enum": ["mermaid"],
            "default": "mermaid",
            "description": "The output format for generated diagrams.",
        },
        "include_relationship_flowchart": {
            "type": "boolean",
            "default": True,
            "description": "Whether to generate relationship flowchart for index.md.",
        },
        "include_class_diagram": {
            "type": "boolean",
            "default": False,
            "description": "Whether to generate class diagram for diagrams chapter.",
        },
        "include_package_diagram": {
            "type": "boolean",
            "default": False,
            "description": "Whether to generate package dependency diagram for diagrams chapter.",
        },
        "include_sequence_diagrams": SEQUENCE_DIAGRAM_SCHEMA,
    },
    "additionalProperties": False,
    # Default for the whole diagram_generation section if it's missing
    "default": {
        # "separate_markup_file_generated" removed
        "format": "mermaid",
        "include_relationship_flowchart": True,
        "include_class_diagram": False,
        "include_package_diagram": False,
        "include_sequence_diagrams": SEQUENCE_DIAGRAM_SCHEMA["default"],
    },
}

# --- Main Configuration Schema (using updated diagram schema) ---
CONFIG_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "project": {
            "type": "object",
            "properties": {"default_name": {"type": ["string", "null"], "default": None}},
            "additionalProperties": False,
            "default": {"default_name": None},
        },
        "source": {
            "type": "object",
            "properties": {
                "default_exclude_patterns": {"type": "array", "items": {"type": "string"}, "default": []},
                "max_file_size_bytes": {"type": "integer", "minimum": 0, "default": DEFAULT_MAX_FILE_SIZE},
                "use_relative_paths": {"type": "boolean", "default": True},
                "language_profiles": {"type": "array", "minItems": 1, "items": LANGUAGE_PROFILE_SCHEMA},
            },
            "required": ["language_profiles"],
            "additionalProperties": False,
        },
        "output": {
            "type": "object",
            "properties": {
                "base_dir": {"type": "string", "default": DEFAULT_OUTPUT_DIR},
                "language": {"type": "string", "default": DEFAULT_LANGUAGE},
                "diagram_generation": DIAGRAM_GENERATION_SCHEMA,  # References updated schema
            },
            "additionalProperties": False,
            "default": {
                "base_dir": DEFAULT_OUTPUT_DIR,
                "language": DEFAULT_LANGUAGE,
                "diagram_generation": DIAGRAM_GENERATION_SCHEMA["default"],  # Uses updated default
            },
        },
        "logging": {
            "type": "object",
            "properties": {
                "log_dir": {"type": "string", "default": DEFAULT_LOG_DIR},
                "log_level": {
                    "type": "string",
                    "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    "default": "INFO",
                },
            },
            "additionalProperties": False,
            "default": {"log_dir": DEFAULT_LOG_DIR, "log_level": "INFO"},
        },
        "cache": {
            "type": "object",
            "properties": {"llm_cache_file": {"type": "string", "default": DEFAULT_CACHE_FILE}},
            "additionalProperties": False,
            "default": {"llm_cache_file": DEFAULT_CACHE_FILE},
        },
        "github": {
            "type": "object",
            "properties": {"token": {"type": ["string", "null"], "default": None}},
            "additionalProperties": False,
            "default": {"token": None},
        },
        "llm": {
            "type": "object",
            "properties": {
                "max_retries": {"type": "integer", "minimum": 0, "default": DEFAULT_LLM_RETRIES},
                "retry_wait_seconds": {"type": "integer", "minimum": 0, "default": DEFAULT_LLM_WAIT},
                "use_cache": {"type": "boolean", "default": True},
                "providers": {"type": "array", "minItems": 1, "items": LLM_PROVIDER_SCHEMA},
            },
            "required": ["providers"],
            "additionalProperties": False,
        },
    },
    "required": ["source", "llm"],
    "additionalProperties": False,
}


# --- Custom Exception ---
class ConfigError(Exception):
    """Custom exception for configuration loading or validation errors."""

    pass


# --- Logger Setup ---
logger = logging.getLogger(__name__)

# --- Helper Functions ---


def _ensure_jsonschema_available() -> None:
    """Raise ImportError if jsonschema is not available."""
    if not JSONSCHEMA_AVAILABLE:
        raise ImportError("The 'jsonschema' library is required for config validation. Please install it.")


def _read_config_file(config_path: Path) -> ConfigDict:
    """Read and parse the JSON configuration file."""
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: '{config_path.resolve()}'")
    try:
        with config_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON syntax in '{config_path.resolve()}': {e}") from e
    except OSError as e:
        raise ConfigError(f"Could not read configuration file '{config_path.resolve()}': {e}") from e


def _validate_schema(config_data: ConfigDict, config_path: Path) -> None:
    """Validate the loaded configuration data against the main JSON schema."""
    _ensure_jsonschema_available()
    assert validate is not None
    assert jsonschema is not None

    try:
        validate(instance=config_data, schema=CONFIG_SCHEMA)
        logger.debug("Configuration schema validation passed for %s.", config_path.name)
    except jsonschema.exceptions.ValidationError as e:
        schema_path = " -> ".join(map(str, e.path)) or "root"
        error_message = f"Configuration error in '{config_path.name}' at '{schema_path}': {e.message}"
        logger.debug("Schema validation failed for instance: %s. Schema: %s", e.instance, e.schema)
        raise ConfigError(error_message) from e
    except Exception as e:
        raise ConfigError(f"Unexpected error during schema validation: {e}") from e


def _resolve_api_key(provider_name: Optional[str], current_key: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Resolve API key from config value or standard environment variables."""
    if current_key is not None:
        return current_key, None

    env_var_map: dict[str, str] = {
        "gemini": ENV_VAR_GEMINI_KEY,
        "vertexai": ENV_VAR_VERTEX_CREDS,
        "anthropic": ENV_VAR_ANTHROPIC_KEY,
        "openai": ENV_VAR_OPENAI_KEY,
        "perplexity": ENV_VAR_PERPLEXITY_KEY,
    }

    env_key_name = env_var_map.get(provider_name) if provider_name else None
    if env_key_name:
        api_key_from_env = os.environ.get(env_key_name)
        if api_key_from_env:
            logger.info(
                "Loaded LLM API key for provider '%s' from environment variable '%s'.", provider_name, env_key_name
            )
            return api_key_from_env, env_key_name
        logger.debug("Environment variable '%s' not set for provider '%s'.", env_key_name, provider_name)

    return None, env_key_name


def _validate_local_llm_config(config: ProviderConfigDict) -> None:
    """Validate configuration specific to local OpenAI-compatible LLM providers."""
    provider = config.get("provider", "local_llm")
    api_base_url = config.get("api_base_url")
    api_key = config.get("api_key")

    if not api_base_url or not isinstance(api_base_url, str):
        raise ConfigError(f"Configuration error for local provider '{provider}': Missing or invalid 'api_base_url'.")
    if api_key:
        logger.info("API key provided for local provider '%s'. Ensure this is required/supported.", provider)
    else:
        logger.debug("No API key provided for local provider '%s'. Using default/no authentication.", provider)


def _validate_vertexai_config(config: ProviderConfigDict, checked_env_var: Optional[str]) -> None:
    """Validate configuration specific to the Vertex AI provider."""
    provider = config.get("provider", "vertexai")
    api_key_or_creds = config.get("api_key")

    if not api_key_or_creds:
        env_var_msg = f" or environment variable '{checked_env_var}'" if checked_env_var else ""
        logger.warning(
            "Vertex AI provider: No explicit API key or credentials file path found in config%s. "
            "Attempting to use Application Default Credentials (ADC). Ensure ADC is configured correctly.",
            env_var_msg,
        )

    if not config.get("vertex_project"):
        if proj_env := os.environ.get(ENV_VAR_GOOGLE_PROJECT):
            config["vertex_project"] = proj_env
            logger.info(
                "Loaded Vertex AI project ID ('%s') from environment variable '%s'.", proj_env, ENV_VAR_GOOGLE_PROJECT
            )
        else:
            raise ConfigError(
                f"Configuration error for provider '{provider}': Missing 'vertex_project' and environment variable '{ENV_VAR_GOOGLE_PROJECT}' is not set."
            )

    if not config.get("vertex_location"):
        if loc_env := os.environ.get(ENV_VAR_GOOGLE_REGION):
            config["vertex_location"] = loc_env
            logger.info(
                "Loaded Vertex AI location ('%s') from environment variable '%s'.", loc_env, ENV_VAR_GOOGLE_REGION
            )
        else:
            raise ConfigError(
                f"Configuration error for provider '{provider}': Missing 'vertex_location' and environment variable '{ENV_VAR_GOOGLE_REGION}' is not set."
            )


def _validate_standard_cloud_config(config: ProviderConfigDict, checked_env_var: Optional[str]) -> None:
    """Validate configuration for standard cloud providers requiring an API key."""
    provider = config.get("provider")
    api_key = config.get("api_key")
    api_base_url = config.get("api_base_url")

    if not api_key:
        env_msg = f" and environment variable '{checked_env_var}' was not set" if checked_env_var else ""
        raise ConfigError(f"Configuration error for cloud provider '{provider}': Missing 'api_key' in config{env_msg}.")

    if api_base_url:
        logger.warning(
            "Configuration warning for cloud provider '%s': 'api_base_url' is set ('%s') but likely unused.",
            provider,
            api_base_url,
        )


def _validate_active_llm_config(active_config: ProviderConfigDict) -> None:
    """Validate the chosen active LLM provider configuration by dispatching."""
    provider = active_config.get("provider")
    is_local = active_config.get("is_local_llm", False)
    api_key = active_config.get("api_key")
    checked_env_var: Optional[str] = None

    logger.debug("Validating active LLM provider config: %s", provider)

    if not is_local:
        resolved_key, checked_env_var = _resolve_api_key(provider, api_key)
        active_config["api_key"] = resolved_key

    if is_local:
        _validate_local_llm_config(active_config)
    elif provider == "vertexai":
        _validate_vertexai_config(active_config, checked_env_var)
    else:
        _validate_standard_cloud_config(active_config, checked_env_var)

    logger.debug("Active LLM provider config validation successful for: %s", provider)


def _validate_github_token(github_config: ConfigDict) -> None:
    """Validate GitHub token presence (from config or environment)."""
    if not isinstance(github_config, dict):
        logger.warning("GitHub configuration section is missing or not a dictionary.")
        return

    if github_config.get("token") is None:
        logger.debug("GitHub token not found in config file. Checking environment variable '%s'.", ENV_VAR_GITHUB_TOKEN)
        if env_github_token := os.environ.get(ENV_VAR_GITHUB_TOKEN):
            github_config["token"] = env_github_token
            logger.info("Loaded GitHub token from environment variable '%s'.", ENV_VAR_GITHUB_TOKEN)
        else:
            logger.warning(
                "No GitHub token found in config file or environment variable '%s'. "
                "Access to private repositories and API rate limits may be affected.",
                ENV_VAR_GITHUB_TOKEN,
            )
    else:
        logger.debug("GitHub token found in configuration file.")


def _ensure_cache_dir(cache_config: ConfigDict) -> None:
    """Ensure the directory for the LLM cache file exists, creating it if necessary."""
    if not isinstance(cache_config, dict):
        logger.warning("Cache configuration section is missing or not a dictionary.")
        return

    cache_file_str = cache_config.get("llm_cache_file", DEFAULT_CACHE_FILE)
    if not cache_file_str or not isinstance(cache_file_str, str):
        logger.warning("Invalid 'llm_cache_file' path configured: '%s'.", cache_file_str)
        return

    try:
        cache_file_path = Path(cache_file_str)
        cache_dir = cache_file_path.parent
        if cache_dir != Path():
            cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("Ensured LLM cache directory exists: %s", cache_dir.resolve())
    except OSError as e:
        logger.error("Could not create cache directory '%s': %s.", cache_dir, e, exc_info=True)
    except Exception as e:
        logger.error("Error processing cache file path '%s': %s.", cache_file_str, e, exc_info=True)


def _apply_defaults_and_validate_sections(config_data: ConfigDict) -> None:
    """Apply default values for missing sections/keys and run specific validations."""
    project_cfg = config_data.setdefault("project", CONFIG_SCHEMA["properties"]["project"]["default"])
    project_cfg.setdefault("default_name", None)

    output_cfg = config_data.setdefault("output", CONFIG_SCHEMA["properties"]["output"]["default"])
    output_cfg.setdefault("base_dir", DEFAULT_OUTPUT_DIR)
    output_cfg.setdefault("language", DEFAULT_LANGUAGE)
    diag_gen_cfg = output_cfg.setdefault("diagram_generation", DIAGRAM_GENERATION_SCHEMA["default"])
    # Apply defaults for diagram generation using updated sub-schemas
    diag_gen_cfg.setdefault("format", "mermaid")
    diag_gen_cfg.setdefault("include_relationship_flowchart", True)
    diag_gen_cfg.setdefault("include_class_diagram", False)
    diag_gen_cfg.setdefault("include_package_diagram", False)
    seq_diag_cfg = diag_gen_cfg.setdefault(
        "include_sequence_diagrams",
        SEQUENCE_DIAGRAM_SCHEMA["default"],  # Use revised default
    )
    seq_diag_cfg.setdefault("enabled", False)
    seq_diag_cfg.setdefault("max_diagrams", 5)
    # 'scenarios' key is intentionally not set here
    # 'separate_markup_file_generated' key is intentionally not set here

    logging_cfg = config_data.setdefault("logging", CONFIG_SCHEMA["properties"]["logging"]["default"])
    logging_cfg.setdefault("log_dir", DEFAULT_LOG_DIR)
    logging_cfg.setdefault("log_level", "INFO")

    cache_cfg = config_data.setdefault("cache", CONFIG_SCHEMA["properties"]["cache"]["default"])
    cache_cfg.setdefault("llm_cache_file", DEFAULT_CACHE_FILE)

    github_cfg = config_data.setdefault("github", CONFIG_SCHEMA["properties"]["github"]["default"])
    github_cfg.setdefault("token", None)

    # Run specific validations after defaults are applied
    _validate_github_token(github_cfg)
    _ensure_cache_dir(cache_cfg)


def _process_llm_config(llm_section: ConfigDict) -> ConfigDict:
    """Find the active LLM provider config, validate it, and merge with common settings."""
    if not isinstance(llm_section, dict):
        raise ConfigError("Configuration format error: 'llm' section must be a dictionary.")

    provider_configs = llm_section.get("providers", [])
    if not isinstance(provider_configs, list):
        raise ConfigError("Configuration format error: 'llm.providers' must be a list.")

    active_provider_config: Optional[ProviderConfigDict] = None
    active_count = 0
    for provider_cfg in provider_configs:
        if isinstance(provider_cfg, dict) and provider_cfg.get("is_active") is True:
            if not all(k in provider_cfg for k in ("provider", "model", "is_local_llm")):
                raise ConfigError(f"Active LLM provider config missing required keys: {provider_cfg}")
            active_provider_config = provider_cfg
            active_count += 1

    if active_count == 0:
        raise ConfigError("Configuration error: No active LLM provider found in 'llm.providers'.")
    if active_count > 1:
        raise ConfigError("Configuration error: Multiple active LLM providers found.")
    if active_provider_config is None:
        raise ConfigError("Internal error: Failed to identify the active LLM provider configuration.")

    _validate_active_llm_config(active_provider_config)

    final_llm_config: ConfigDict = {
        "max_retries": llm_section.get("max_retries", DEFAULT_LLM_RETRIES),
        "retry_wait_seconds": llm_section.get("retry_wait_seconds", DEFAULT_LLM_WAIT),
        "use_cache": llm_section.get("use_cache", True),
        **active_provider_config,
    }
    return final_llm_config


def _process_source_config(source_section: ConfigDict) -> ConfigDict:
    """Find active language profile, merge with common source settings."""
    if not isinstance(source_section, dict):
        raise ConfigError("Configuration format error: 'source' section must be a dictionary.")

    language_profiles = source_section.get("language_profiles", [])
    if not isinstance(language_profiles, list):
        raise ConfigError("Configuration format error: 'source.language_profiles' must be a list.")

    active_profile: Optional[LanguageProfileDict] = None
    active_count = 0
    for profile in language_profiles:
        if isinstance(profile, dict) and profile.get("is_active") is True:
            if not all(k in profile for k in ("language", "default_include_patterns")):
                raise ConfigError(f"Active language profile missing required keys: {profile}")
            active_profile = profile
            active_count += 1

    if active_count == 0:
        raise ConfigError("Configuration error: No active language profile found.")
    if active_count > 1:
        raise ConfigError("Configuration error: Multiple active language profiles found.")
    if active_profile is None:
        raise ConfigError("Internal error: Failed to identify the active language profile.")

    final_source_config: ConfigDict = {
        "default_exclude_patterns": source_section.get("default_exclude_patterns", []),
        "max_file_size_bytes": source_section.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE),
        "use_relative_paths": source_section.get("use_relative_paths", True),
    }
    final_source_config.update(active_profile)

    if active_profile.get("max_file_size_bytes") is not None:
        final_source_config["max_file_size_bytes"] = active_profile["max_file_size_bytes"]
    if active_profile.get("use_relative_paths") is not None:
        final_source_config["use_relative_paths"] = active_profile["use_relative_paths"]

    final_source_config.pop("is_active", None)
    logger.debug("Processed source config using active language profile: %s", active_profile.get("language"))
    return final_source_config


# --- Main load_config Function ---
def load_config(config_path_str: str = "config.json") -> ConfigDict:
    """Load, validate, process, and return the application configuration.

    Orchestrates the configuration loading process: Reads JSON, validates against schema,
    processes LLM and Source sections (selecting active profiles, resolving keys),
    applies defaults, and performs final checks.

    Args:
        config_path_str: Path string to the configuration JSON file.

    Returns:
        A dictionary representing the fully validated, processed, and defaulted configuration.

    Raises:
        FileNotFoundError: If the specified config file does not exist.
        ConfigError: If the config file is invalid JSON, fails schema validation,
                     or contains logical errors (e.g., no active LLM provider).
        ImportError: If `jsonschema` is required but not installed.

    """
    logger.info("Loading configuration from: %s", config_path_str)
    config_path = Path(config_path_str)

    config_data = _read_config_file(config_path)
    _validate_schema(config_data, config_path)  # Uses updated schema

    config_data["llm"] = _process_llm_config(config_data.get("llm", {}))
    config_data["source"] = _process_source_config(config_data.get("source", {}))
    _apply_defaults_and_validate_sections(config_data)  # Uses updated schema defaults

    logger.info("Configuration loaded and processed successfully.")
    return config_data


# End of src/sourcelens/config.py
