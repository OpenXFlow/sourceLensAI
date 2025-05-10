# src/sourcelens/config.py

"""Load, validate, and process configuration for the SourceLens application.

This module handles reading settings from a JSON file, validating the structure
against a defined JSON schema, resolving secrets from environment variables,
selecting active LLM and language profiles, applying default values, and ensuring
necessary directories (cache, logs) exist. It provides a single, validated
configuration dictionary for the application. Includes detailed schema definitions
for all configurable sections.
"""

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional, TypeAlias

# Safe imports for optional dependencies
try:
    import jsonschema
    from jsonschema import validate

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    validate = None  # type: ignore[assignment]
    JSONSCHEMA_AVAILABLE = False

if TYPE_CHECKING:
    from jsonschema.exceptions import ValidationError


# --- Type Aliases ---
ConfigDict: TypeAlias = dict[str, Any]
ProviderConfigDict: TypeAlias = dict[str, Any]
LanguageProfileDict: TypeAlias = dict[str, Any]

# --- Constants ---
DEFAULT_CACHE_FILE: Final[str] = ".cache/llm_cache.json"
DEFAULT_LOG_DIR: Final[str] = "logs"
DEFAULT_OUTPUT_DIR: Final[str] = "output"
DEFAULT_LANGUAGE: Final[str] = "english"
DEFAULT_MAX_FILE_SIZE: Final[int] = 150000
DEFAULT_LLM_RETRIES: Final[int] = 3
DEFAULT_LLM_WAIT: Final[int] = 10
DEFAULT_SOURCE_INDEX_PARSER: Final[str] = "none"  # Default for language profiles
# Environment variable names
ENV_VAR_GOOGLE_PROJECT: Final[str] = "GOOGLE_CLOUD_PROJECT"
ENV_VAR_GOOGLE_REGION: Final[str] = "GOOGLE_CLOUD_REGION"
ENV_VAR_GITHUB_TOKEN: Final[str] = "GITHUB_TOKEN"
ENV_VAR_GEMINI_KEY: Final[str] = "GEMINI_API_KEY"
ENV_VAR_VERTEX_CREDS: Final[str] = "GOOGLE_APPLICATION_CREDENTIALS"
ENV_VAR_ANTHROPIC_KEY: Final[str] = "ANTHROPIC_API_KEY"
ENV_VAR_OPENAI_KEY: Final[str] = "OPENAI_API_KEY"
ENV_VAR_PERPLEXITY_KEY: Final[str] = "PERPLEXITY_API_KEY"


# --- JSON Schema Definitions ---
LLM_PROVIDER_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "is_active": {"type": "boolean"},
        "is_local_llm": {"type": "boolean"},
        "provider": {"type": "string"},
        "model": {"type": "string"},
        "api_key": {"type": ["string", "null"]},
        "api_base_url": {"type": ["string", "null"]},
        "vertex_project": {"type": ["string", "null"]},
        "vertex_location": {"type": ["string", "null"]},
    },
    "required": ["is_active", "is_local_llm", "provider", "model"],
    "additionalProperties": False,
}

LANGUAGE_PROFILE_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "is_active": {"type": "boolean"},
        "language": {"type": "string"},
        "default_include_patterns": {"type": "array", "items": {"type": "string"}, "default": []},
        "max_file_size_bytes": {"type": ["integer", "null"], "minimum": 0, "default": None},
        "use_relative_paths": {"type": ["boolean", "null"], "default": None},
        "source_index_parser": {
            "type": "string",
            "enum": ["ast", "llm", "none"],
            "default": DEFAULT_SOURCE_INDEX_PARSER,
            "description": ("Parser for detailed source index: 'ast' (Python only), 'llm', or 'none'."),
        },
    },
    "required": ["is_active", "language", "source_index_parser"],
    "additionalProperties": False,
}

SEQUENCE_DIAGRAM_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "default": False},
        "max_diagrams": {"type": "integer", "minimum": 1, "default": 5},
    },
    "additionalProperties": False,
    "default": {"enabled": False, "max_diagrams": 5},
}

DIAGRAM_GENERATION_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "format": {"type": "string", "enum": ["mermaid"], "default": "mermaid"},
        "include_relationship_flowchart": {"type": "boolean", "default": True},
        "include_class_diagram": {"type": "boolean", "default": False},
        "include_package_diagram": {"type": "boolean", "default": False},
        "include_sequence_diagrams": SEQUENCE_DIAGRAM_SCHEMA,
    },
    "additionalProperties": False,
    "default": {
        "format": "mermaid",
        "include_relationship_flowchart": True,
        "include_class_diagram": False,
        "include_package_diagram": False,
        "include_sequence_diagrams": SEQUENCE_DIAGRAM_SCHEMA["default"],
    },
}

# SOURCE_INDEX_SCHEMA is removed. 'include_source_index' moved to OUTPUT_SCHEMA.

OUTPUT_SCHEMA: ConfigDict = {  # Added a more explicit OUTPUT_SCHEMA for clarity
    "type": "object",
    "properties": {
        "base_dir": {"type": "string", "default": DEFAULT_OUTPUT_DIR},
        "language": {"type": "string", "default": DEFAULT_LANGUAGE},
        "diagram_generation": DIAGRAM_GENERATION_SCHEMA,
        "include_source_index": {  # Moved from diagram_generation to direct output property
            "type": "boolean",
            "default": False,
            "description": "Globally controls if the source index (code_inventory.md) should be generated.",
        },
    },
    "additionalProperties": False,
    "default": {
        "base_dir": DEFAULT_OUTPUT_DIR,
        "language": DEFAULT_LANGUAGE,
        "diagram_generation": DIAGRAM_GENERATION_SCHEMA["default"],
        "include_source_index": False,  # Default for the new global flag
    },
}


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
        "output": OUTPUT_SCHEMA,  # Use the new OUTPUT_SCHEMA
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


# --- Logger Setup ---
logger = logging.getLogger(__name__)


# --- Helper Functions ---
def _ensure_jsonschema_available() -> None:
    """Raise ImportError if jsonschema is not available.

    Raises:
        ImportError: If the jsonschema library is not installed and available.

    """
    if not JSONSCHEMA_AVAILABLE:
        raise ImportError("The 'jsonschema' library is required for config validation. Please install it.")


def _read_config_file(config_path: Path) -> ConfigDict:
    """Read and parse the JSON configuration file.

    Args:
        config_path: Path object to the configuration file.

    Returns:
        The parsed configuration data as a dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ConfigError: If the file cannot be read or parsed as JSON.

    """
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
    """Validate the loaded configuration data against the main JSON schema.

    Args:
        config_data: The configuration data loaded from the file.
        config_path: Path object to the configuration file (for error reporting).

    Raises:
        RuntimeError: If jsonschema components are unexpectedly unavailable.
        ConfigError: If schema validation fails or an unexpected error occurs.
        ImportError: If jsonschema library is not installed.

    """
    _ensure_jsonschema_available()
    if validate is None:
        raise RuntimeError("jsonschema 'validate' function is not available.")
    if (
        jsonschema is None
        or not hasattr(jsonschema, "exceptions")
        or not hasattr(jsonschema.exceptions, "ValidationError")
    ):
        raise RuntimeError("'jsonschema.exceptions.ValidationError' is not available for exception handling.")

    try:
        # jsonschema.exceptions.ValidationError is checked by hasattr
        validation_error_type: type[ValidationError] = jsonschema.exceptions.ValidationError  # type: ignore[attr-defined]
        validate(instance=config_data, schema=CONFIG_SCHEMA)
        logger.debug("Configuration schema validation passed for %s.", config_path.name)
    except validation_error_type as e_val_err:
        schema_path_str = " -> ".join(map(str, e_val_err.path)) if e_val_err.path else "root"
        error_message = f"Configuration error in '{config_path.name}' at '{schema_path_str}': {e_val_err.message}"
        logger.debug(
            "Schema validation failed. Instance: %s. Path: %s. Schema: %s",
            e_val_err.instance,
            schema_path_str,
            e_val_err.schema,
        )
        raise ConfigError(error_message) from e_val_err
    except Exception as e:  # pylint: disable=broad-except
        raise ConfigError(f"Unexpected error during schema validation: {e}") from e


def _resolve_api_key(provider_name: Optional[str], current_key: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Resolve API key from config value or standard environment variables.

    Args:
        provider_name: The name of the LLM provider (e.g., "gemini", "openai").
        current_key: The API key value currently set in the configuration.

    Returns:
        A tuple containing:
            - The resolved API key (str or None).
            - The name of the environment variable used (str or None).

    """
    if current_key is not None:
        return current_key, None

    env_var_map: dict[str, str] = {
        "gemini": ENV_VAR_GEMINI_KEY,
        "vertexai": ENV_VAR_VERTEX_CREDS,
        "anthropic": ENV_VAR_ANTHROPIC_KEY,
        "openai": ENV_VAR_OPENAI_KEY,
        "perplexity": ENV_VAR_PERPLEXITY_KEY,
    }
    env_key_name = env_var_map.get(str(provider_name)) if provider_name else None

    if env_key_name:
        api_key_from_env = os.environ.get(env_key_name)
        if api_key_from_env:
            logger.info(
                "Loaded LLM API key for provider '%s' from environment variable '%s'.",
                provider_name,
                env_key_name,
            )
            return api_key_from_env, env_key_name
        logger.debug("Environment variable '%s' not set for provider '%s'.", env_key_name, provider_name)
    return None, env_key_name


def _validate_local_llm_config(config: ProviderConfigDict) -> None:
    """Validate configuration specific to local OpenAI-compatible LLM providers.

    Args:
        config: The LLM provider's configuration dictionary.

    Raises:
        ConfigError: If 'api_base_url' is missing or invalid.

    """
    provider = config.get("provider", "local_llm")
    api_base_url = config.get("api_base_url")
    api_key = config.get("api_key")

    if not api_base_url or not isinstance(api_base_url, str):
        raise ConfigError(f"For local provider '{provider}': Missing or invalid 'api_base_url'.")
    if api_key:
        logger.info("API key provided for local provider '%s'. Ensure this is supported.", provider)


def _validate_vertexai_config(config: ProviderConfigDict, checked_env_var: Optional[str]) -> None:
    """Validate configuration specific to the Vertex AI provider.

    Ensures 'vertex_project' and 'vertex_location' are set, either in config
    or via environment variables.

    Args:
        config: The Vertex AI provider's configuration dictionary.
        checked_env_var: The environment variable that was checked for credentials.

    Raises:
        ConfigError: If project or location is missing and not found in env.

    """
    provider = config.get("provider", "vertexai")
    api_key_or_creds = config.get("api_key")

    if not api_key_or_creds:
        env_var_msg = f" or environment variable '{checked_env_var}'" if checked_env_var else ""
        logger.warning(
            "Vertex AI: No API key/creds path in config%s. Using Application Default Credentials.",
            env_var_msg,
        )

    if not config.get("vertex_project"):
        proj_env = os.environ.get(ENV_VAR_GOOGLE_PROJECT)
        if proj_env:
            config["vertex_project"] = proj_env
            logger.info("Loaded Vertex AI project '%s' from env var '%s'.", proj_env, ENV_VAR_GOOGLE_PROJECT)
        else:
            raise ConfigError(
                f"For provider '{provider}': Missing 'vertex_project' and env var '{ENV_VAR_GOOGLE_PROJECT}' not set."
            )
    if not config.get("vertex_location"):
        loc_env = os.environ.get(ENV_VAR_GOOGLE_REGION)
        if loc_env:
            config["vertex_location"] = loc_env
            logger.info("Loaded Vertex AI location '%s' from env var '%s'.", loc_env, ENV_VAR_GOOGLE_REGION)
        else:
            raise ConfigError(
                f"For provider '{provider}': Missing 'vertex_location' and env var '{ENV_VAR_GOOGLE_REGION}' not set."
            )


def _validate_standard_cloud_config(config: ProviderConfigDict, checked_env_var: Optional[str]) -> None:
    """Validate configuration for standard cloud providers requiring an API key.

    Args:
        config: The cloud provider's configuration dictionary.
        checked_env_var: The environment variable that was checked for the API key.

    Raises:
        ConfigError: If 'api_key' is missing and not found in env.

    """
    provider = config.get("provider")
    api_key = config.get("api_key")
    api_base_url = config.get("api_base_url")

    if not api_key:
        env_msg = f" and environment variable '{checked_env_var}' was not set" if checked_env_var else ""
        raise ConfigError(f"For cloud provider '{provider}': Missing 'api_key' in config{env_msg}.")
    if api_base_url:
        logger.warning(
            "For cloud provider '%s': 'api_base_url' ('%s') is set but likely unused.",
            provider,
            api_base_url,
        )


def _validate_active_llm_config(active_config: ProviderConfigDict) -> None:
    """Validate the chosen active LLM provider configuration by dispatching.

    Args:
        active_config: The configuration dictionary for the active LLM provider.

    Raises:
        ConfigError: If validation for the specific provider type fails.
        ValueError: If provider name is missing.

    """
    provider = active_config.get("provider")
    if not isinstance(provider, str):
        raise ValueError("Active LLM provider config missing 'provider' name.")

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
    """Validate GitHub token presence (from config or environment).

    Updates the `github_config` dictionary in-place if token is found in env.

    Args:
        github_config: The 'github' section dictionary from the configuration.

    """
    if not isinstance(github_config, dict):
        logger.warning("GitHub config section missing/invalid. Token checks skipped.")
        return

    if github_config.get("token") is None:
        logger.debug("GitHub token not in config. Checking env var '%s'.", ENV_VAR_GITHUB_TOKEN)
        if env_github_token := os.environ.get(ENV_VAR_GITHUB_TOKEN):
            github_config["token"] = env_github_token
            logger.info("Loaded GitHub token from env var '%s'.", ENV_VAR_GITHUB_TOKEN)
        else:
            logger.warning(
                "No GitHub token in config or env var '%s'. Private repo access/API rates may be affected.",
                ENV_VAR_GITHUB_TOKEN,
            )
    else:
        logger.debug("GitHub token found in configuration file.")


def _ensure_directory_exists(dir_path_str: Optional[str], dir_purpose: str, default_path: str) -> None:
    """Ensure a directory exists, creating it if necessary.

    Args:
        dir_path_str: The directory path string from config (can be None).
        dir_purpose: A string describing the directory's purpose (for logging).
        default_path: The default path string to use if dir_path_str is None or invalid.

    """
    path_to_check_str = dir_path_str if isinstance(dir_path_str, str) and dir_path_str else default_path
    if not path_to_check_str:  # Should not happen if default_path is always set
        logger.error("Cannot ensure %s directory: No valid path provided.", dir_purpose)
        return

    try:
        dir_to_ensure = Path(path_to_check_str)
        if dir_to_ensure != Path():  # Avoid trying to mkdir for a filename without parent
            dir_to_ensure.mkdir(parents=True, exist_ok=True)
            logger.debug("Ensured %s directory exists: %s", dir_purpose, dir_to_ensure.resolve())
    except OSError as e:
        logger.error("Could not create %s directory '%s': %s.", dir_purpose, dir_to_ensure, e, exc_info=True)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error ensuring %s directory for path '%s': %s.", dir_purpose, path_to_check_str, e, exc_info=True)


def _apply_defaults_and_validate_sections(config_data: ConfigDict) -> None:
    """Apply default values for missing sections/keys and run specific validations.

    Modifies `config_data` in-place.

    Args:
        config_data: The main configuration dictionary.

    """
    project_cfg = config_data.setdefault("project", CONFIG_SCHEMA["properties"]["project"]["default"])
    project_cfg.setdefault("default_name", None)

    output_cfg = config_data.setdefault("output", OUTPUT_SCHEMA["default"])
    output_cfg.setdefault("base_dir", DEFAULT_OUTPUT_DIR)
    output_cfg.setdefault("language", DEFAULT_LANGUAGE)
    output_cfg.setdefault("include_source_index", False)  # Default for new flag

    diag_gen_cfg = output_cfg.setdefault("diagram_generation", DIAGRAM_GENERATION_SCHEMA["default"])
    diag_gen_cfg.setdefault("format", "mermaid")
    # Other diagram_generation defaults are handled by its own schema default

    logging_cfg = config_data.setdefault("logging", CONFIG_SCHEMA["properties"]["logging"]["default"])
    logging_cfg.setdefault("log_dir", DEFAULT_LOG_DIR)
    logging_cfg.setdefault("log_level", "INFO")
    _ensure_directory_exists(logging_cfg.get("log_dir"), "logging", DEFAULT_LOG_DIR)

    cache_cfg = config_data.setdefault("cache", CONFIG_SCHEMA["properties"]["cache"]["default"])
    cache_cfg.setdefault("llm_cache_file", DEFAULT_CACHE_FILE)
    _ensure_directory_exists(
        Path(str(cache_cfg.get("llm_cache_file"))).parent.as_posix(),
        "LLM cache",
        Path(DEFAULT_CACHE_FILE).parent.as_posix(),
    )

    github_cfg = config_data.setdefault("github", CONFIG_SCHEMA["properties"]["github"]["default"])
    github_cfg.setdefault("token", None)
    _validate_github_token(github_cfg)


def _process_llm_config(llm_section: ConfigDict) -> ConfigDict:
    """Find the active LLM provider config, validate it, and merge with common settings.

    Args:
        llm_section: The 'llm' dictionary from the loaded configuration.

    Returns:
        A dictionary containing the merged configuration for the active LLM provider.

    Raises:
        ConfigError: If 'llm' section or 'providers' list is malformed,
                     no active provider found, multiple active providers found,
                     or active provider's config fails validation.
        ValueError: If provider name is missing in active config.

    """
    if not isinstance(llm_section, dict):
        raise ConfigError("Config error: 'llm' section must be a dictionary.")

    provider_configs = llm_section.get("providers", [])
    if not isinstance(provider_configs, list) or not provider_configs:  # Ensure not empty
        raise ConfigError("Config error: 'llm.providers' must be a non-empty list.")

    active_provider_configs: list[ProviderConfigDict] = [
        p_cfg for p_cfg in provider_configs if isinstance(p_cfg, dict) and p_cfg.get("is_active") is True
    ]

    if not active_provider_configs:
        raise ConfigError("Config error: No active LLM provider in 'llm.providers'.")
    if len(active_provider_configs) > 1:
        raise ConfigError("Config error: Multiple active LLM providers. Set only one to 'is_active: true'.")

    active_provider_config = active_provider_configs[0]
    if not all(k in active_provider_config for k in ("provider", "model", "is_local_llm")):
        raise ConfigError(f"Active LLM provider config missing required keys: {active_provider_config}")

    _validate_active_llm_config(active_provider_config)

    final_llm_config: ConfigDict = {
        "max_retries": llm_section.get("max_retries", DEFAULT_LLM_RETRIES),
        "retry_wait_seconds": llm_section.get("retry_wait_seconds", DEFAULT_LLM_WAIT),
        "use_cache": llm_section.get("use_cache", True),
        **active_provider_config,
    }
    return final_llm_config


def _find_active_language_profile(language_profiles: list[Any]) -> LanguageProfileDict:
    """Iterate through language profiles and return the first active one.

    Args:
        language_profiles: The list of language profile dictionaries.

    Returns:
        The first active language profile dictionary.

    Raises:
        ConfigError: If 'language_profiles' is not a list, no active profile
                     is found, or multiple active profiles are found.

    """
    if not isinstance(language_profiles, list) or not language_profiles:  # Ensure not empty
        raise ConfigError("Config error: 'source.language_profiles' must be a non-empty list.")

    active_profiles: list[LanguageProfileDict] = [
        profile for profile in language_profiles if isinstance(profile, dict) and profile.get("is_active") is True
    ]

    if not active_profiles:
        raise ConfigError("Config error: No active language profile in 'source.language_profiles'.")
    if len(active_profiles) > 1:
        raise ConfigError("Config error: Multiple active language profiles. Set only one to 'is_active: true'.")

    active_profile = active_profiles[0]
    # Check for essential keys after finding the active profile
    required_keys = ("language", "default_include_patterns", "source_index_parser")
    if not all(k in active_profile for k in required_keys):
        missing = [k for k in required_keys if k not in active_profile]
        raise ConfigError(
            f"Active language profile missing required key(s): {', '.join(missing)}. Profile: {active_profile}"
        )

    return active_profile


def _process_source_config(source_section: ConfigDict) -> ConfigDict:
    """Find active language profile and merge with common source settings.

    Args:
        source_section: The 'source' dictionary from the loaded configuration.

    Returns:
        A dictionary containing the merged source configuration for the active profile.

    Raises:
        ConfigError: If 'source' section or 'language_profiles' list is malformed,
                     or if active language profile validation fails.

    """
    if not isinstance(source_section, dict):
        raise ConfigError("Config error: 'source' section must be a dictionary.")

    active_profile = _find_active_language_profile(source_section.get("language_profiles", []))

    final_source_config: ConfigDict = {
        "default_exclude_patterns": source_section.get("default_exclude_patterns", []),
        "max_file_size_bytes": source_section.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE),
        "use_relative_paths": source_section.get("use_relative_paths", True),
    }
    # Overlay active profile settings (these take precedence)
    final_source_config.update(active_profile)

    # Explicitly override with profile's specific values if they exist and are not None
    if active_profile.get("max_file_size_bytes") is not None:
        final_source_config["max_file_size_bytes"] = active_profile["max_file_size_bytes"]
    if active_profile.get("use_relative_paths") is not None:
        final_source_config["use_relative_paths"] = active_profile["use_relative_paths"]
    # source_index_parser is now directly part of the active_profile and will be included.

    final_source_config.pop("is_active", None)
    logger.debug("Processed source config using active lang profile: %s", active_profile.get("language"))
    return final_source_config


# --- Main load_config Function ---
def load_config(config_path_str: str = "config.json") -> ConfigDict:
    """Load, validate, process, and return the application configuration.

    Orchestrates reading, schema validation, applying defaults, and processing
    specific sections like LLM and source configurations.

    Args:
        config_path_str: The path string to the configuration JSON file.
                         Defaults to "config.json".

    Returns:
        The fully processed and validated configuration dictionary.

    Raises:
        ConfigError: If any step of configuration loading or processing fails.
        FileNotFoundError: If the configuration file is not found.
        ImportError: If jsonschema is required but not installed.

    """
    logger.info("Loading configuration from: %s", config_path_str)
    config_path = Path(config_path_str).resolve()
    config_data = _read_config_file(config_path)
    _validate_schema(config_data, config_path)

    # Apply defaults before processing sections that depend on them or select active profiles
    _apply_defaults_and_validate_sections(config_data)

    # Process LLM and Source sections to select active profiles and merge settings
    config_data["llm"] = _process_llm_config(config_data.get("llm", {}))
    config_data["source"] = _process_source_config(config_data.get("source", {}))

    logger.info("Configuration loaded and processed successfully.")
    if logger.isEnabledFor(logging.DEBUG):
        try:
            log_config_copy = json.loads(json.dumps(config_data))  # Deep copy for logging
            if log_config_copy.get("llm", {}).get("api_key"):
                log_config_copy["llm"]["api_key"] = "***REDACTED***"
            if log_config_copy.get("github", {}).get("token"):
                log_config_copy["github"]["token"] = "***REDACTED***"
            logger.debug("Final processed config data: %s", json.dumps(log_config_copy, indent=2))
        except (TypeError, ValueError) as dump_error:  # pragma: no cover
            logger.debug("Could not serialize final config for debug logging: %s", dump_error)

    return config_data


# End of src/sourcelens/config.py
