# src/sourcelens/config.py

"""Configuration loading and validation for the SourceLens application.

Handles loading settings from a JSON file, validating against a schema,
selecting active LLM/language profiles, integrating environment variables,
and setting defaults. Includes configuration for diagram generation options.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional, TypeAlias

import jsonschema
from jsonschema import validate

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
GOOGLE_CLOUD_PROJECT_ENV_VAR = "GOOGLE_CLOUD_PROJECT"
GOOGLE_CLOUD_REGION_ENV_VAR = "GOOGLE_CLOUD_REGION"
GITHUB_TOKEN_ENV_VAR = "GITHUB_TOKEN"  # noqa: S105

# --- Sub-Schemas ---
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
        "default_include_patterns": {"type": "array", "items": {"type": "string"}},
        "max_file_size_bytes": {"type": ["integer", "null"], "minimum": 0},
        "use_relative_paths": {"type": ["boolean", "null"]},
    },
    "required": ["is_active", "language", "default_include_patterns"],
    "additionalProperties": False,
}

# --- New Sub-Schema for Diagram Generation ---
DIAGRAM_GENERATION_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "separate_markup_file_generated": {"type": "boolean", "default": False},
        "format": {"type": "string", "enum": ["mermaid"], "default": "mermaid"},
        "include_relationship_flowchart": {"type": "boolean", "default": True},
        "include_class_diagram": {"type": "boolean", "default": False},
        "include_package_diagram": {"type": "boolean", "default": False},
        "include_sequence_diagrams": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "max_diagrams": {"type": "integer", "minimum": 1, "default": 5},
                "scenarios": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "additionalProperties": False,
            # Default for the whole object if missing in config
            "default": {"enabled": False, "max_diagrams": 5, "scenarios": []},
        },
    },
    "additionalProperties": False,
    # Default for the whole section if missing in config
    "default": {
        "separate_markup_file_generated": False,
        "format": "mermaid",
        "include_relationship_flowchart": True,
        "include_class_diagram": False,
        "include_package_diagram": False,
        "include_sequence_diagrams": {"enabled": False, "max_diagrams": 5, "scenarios": []},
    },
}


# --- Main Configuration Schema (Updated) ---
CONFIG_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "project": {
            "type": "object",
            "properties": {"default_name": {"type": ["string", "null"]}},
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
                # --- Integrate Diagram Schema ---
                "diagram_generation": DIAGRAM_GENERATION_SCHEMA,
            },
            "required": [],  # Output section itself is not required
            "additionalProperties": False,
            # Default for the entire output section
            "default": {
                "base_dir": DEFAULT_OUTPUT_DIR,
                "language": DEFAULT_LANGUAGE,
                "diagram_generation": DIAGRAM_GENERATION_SCHEMA["default"],  # Use sub-schema default
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
            "required": [],
            "additionalProperties": False,
            "default": {"log_dir": DEFAULT_LOG_DIR, "log_level": "INFO"},
        },
        "cache": {
            "type": "object",
            "properties": {"llm_cache_file": {"type": "string", "default": DEFAULT_CACHE_FILE}},
            "required": [],
            "additionalProperties": False,
            "default": {"llm_cache_file": DEFAULT_CACHE_FILE},
        },
        "github": {
            "type": "object",
            "properties": {"token": {"type": ["string", "null"], "default": None}},
            "required": [],
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
    "required": ["source", "llm"],  # Only source and llm are strictly required top-level
    "additionalProperties": False,
}


class ConfigError(Exception):
    """Custom exception for configuration loading or validation errors."""

    pass


# --- Helper Functions (Unchanged) ---
def _read_config_file(config_path: Path) -> ConfigDict:
    """Read and parse the JSON configuration file."""
    # ... implementation unchanged ...
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: '{config_path}'")
    try:
        with config_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in '{config_path}': {e}") from e
    except OSError as e:
        raise ConfigError(f"Could not read '{config_path}': {e}") from e


def _validate_schema(config_data: ConfigDict, config_path: Path) -> None:
    """Validate the loaded configuration data against the main schema."""
    # ... implementation unchanged ...
    try:
        validate(instance=config_data, schema=CONFIG_SCHEMA)
    except jsonschema.exceptions.ValidationError as e:
        path_str = ".".join(map(str, e.path)) or "root"
        raise ConfigError(f"Config validation failed in '{config_path}': {e.message} (at {path_str})") from e
    except Exception as e:
        raise ConfigError(f"Unexpected schema validation error: {e}") from e


def _resolve_api_key(provider: Optional[str], current_key: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Resolve API key from config or environment variables."""
    # ... implementation unchanged ...
    if current_key:
        return current_key, None
    env_var_map = {
        "gemini": "GEMINI_API_KEY",
        "vertexai": "GOOGLE_APPLICATION_CREDENTIALS",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
    }
    env_key_name = env_var_map.get(provider) if provider else None
    if env_key_name and (api_key_from_env := os.environ.get(env_key_name)):
        logging.info("Loaded LLM API key from env var %s.", env_key_name)
        return api_key_from_env, env_key_name
    return None, env_key_name


def _validate_local_llm_config(config: ProviderConfigDict) -> None:
    """Validate configuration specific to local LLM providers."""
    # ... implementation unchanged ...
    provider = config.get("provider")
    api_base_url = config.get("api_base_url")
    api_key = config.get("api_key")
    if not api_base_url or not isinstance(api_base_url, str):
        raise ConfigError(f"Missing/invalid 'api_base_url' for local provider '{provider}'.")
    if api_key:
        logging.warning("API key for local provider '%s' likely unused.", provider)


def _validate_vertexai_config(config: ProviderConfigDict, checked_env_var: Optional[str]) -> None:
    """Validate configuration specific to the Vertex AI provider."""
    # ... implementation unchanged ...
    provider = config.get("provider", "vertexai")
    api_key = config.get("api_key")
    if not api_key:
        env_var_msg = f"or {checked_env_var} env var " if checked_env_var else ""
        logging.warning("Vertex AI: No explicit API key found in config %s. Assuming ADC.", env_var_msg)
    if not config.get("vertex_project"):
        if proj_env := os.environ.get(GOOGLE_CLOUD_PROJECT_ENV_VAR):
            config["vertex_project"] = proj_env
            logging.info("Loaded Vertex AI project ID from %s env var.", GOOGLE_CLOUD_PROJECT_ENV_VAR)
        else:
            raise ConfigError(f"Missing 'vertex_project' for provider '{provider}'.")
    if not config.get("vertex_location"):
        if loc_env := os.environ.get(GOOGLE_CLOUD_REGION_ENV_VAR):
            config["vertex_location"] = loc_env
            logging.info("Loaded Vertex AI location from %s env var.", GOOGLE_CLOUD_REGION_ENV_VAR)
        else:
            raise ConfigError(f"Missing 'vertex_location' for provider '{provider}'.")


def _validate_standard_cloud_config(config: ProviderConfigDict, checked_env_var: Optional[str]) -> None:
    """Validate configuration for standard cloud providers requiring an API key."""
    # ... implementation unchanged ...
    provider = config.get("provider")
    api_key = config.get("api_key")
    api_base_url = config.get("api_base_url")
    if not api_key:
        env_msg = f" and env var '{checked_env_var}' not set" if checked_env_var else ""
        raise ConfigError(f"Missing 'api_key' in config{env_msg} for provider '{provider}'.")
    if api_base_url:
        logging.warning("'api_base_url' set but likely unused for cloud provider '%s'.", provider)


def _validate_active_llm_config(active_config: ProviderConfigDict) -> None:
    """Validate the chosen active LLM provider config by dispatching."""
    # ... implementation unchanged ...
    provider = active_config.get("provider")
    is_local = active_config.get("is_local_llm", False)
    api_key = active_config.get("api_key")
    checked_env_var: Optional[str] = None
    if not is_local:
        resolved_key, checked_env_var = _resolve_api_key(provider, api_key)
        active_config["api_key"] = resolved_key
    if is_local:
        _validate_local_llm_config(active_config)
    elif provider == "vertexai":
        _validate_vertexai_config(active_config, checked_env_var)
    else:
        _validate_standard_cloud_config(active_config, checked_env_var)


def _validate_github_token(github_config: ConfigDict) -> None:
    """Validate GitHub token presence (from config or environment)."""
    # ... implementation unchanged ...
    if not isinstance(github_config, dict):
        logging.warning("GitHub config not dict.")
        return
    if not github_config.get("token"):
        if env_github_token := os.environ.get(GITHUB_TOKEN_ENV_VAR):
            github_config["token"] = env_github_token
            logging.info("Loaded GitHub token from env var %s.", GITHUB_TOKEN_ENV_VAR)
        else:
            logging.warning("No GitHub token in config or %s env var.", GITHUB_TOKEN_ENV_VAR)


def _ensure_cache_dir(cache_config: ConfigDict) -> None:
    """Ensure the directory for the LLM cache file exists."""
    # ... implementation unchanged ...
    if not isinstance(cache_config, dict):
        logging.warning("Cache config not dict.")
        return
    cache_file_str = cache_config.get("llm_cache_file", DEFAULT_CACHE_FILE)
    if not cache_file_str or not isinstance(cache_file_str, str):
        logging.warning("LLM cache path invalid.")
        return
    cache_dir = Path(cache_file_str).parent
    if cache_dir != Path():
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logging.error("Could not create cache dir '%s': %s.", cache_dir, e)


def _process_llm_config(llm_section: ConfigDict) -> ConfigDict:
    """Find the active LLM provider config and merge it with common settings."""
    # ... implementation unchanged ...
    if not isinstance(llm_section, dict):
        raise ConfigError("'llm' section must be dict.")
    provider_configs = llm_section.get("providers", [])
    active_provider_config: Optional[ProviderConfigDict] = None
    active_count = 0
    if not isinstance(provider_configs, list):
        raise ConfigError("'llm.providers' must be list.")
    for provider_cfg in provider_configs:
        if isinstance(provider_cfg, dict) and provider_cfg.get("is_active") is True:
            if not all(k in provider_cfg for k in ("provider", "model", "is_local_llm")):
                raise ConfigError(f"Active provider config missing keys: {provider_cfg}")
            active_provider_config = provider_cfg
            active_count += 1
    if active_count == 0:
        raise ConfigError("No active LLM provider found.")
    if active_count > 1:
        raise ConfigError("Multiple active LLM providers found.")
    if active_provider_config is None:
        raise ConfigError("Internal error: No active LLM config identified.")
    final_llm_config: ConfigDict = {
        "max_retries": llm_section.get("max_retries", DEFAULT_LLM_RETRIES),
        "retry_wait_seconds": llm_section.get("retry_wait_seconds", DEFAULT_LLM_WAIT),
        "use_cache": llm_section.get("use_cache", True),
        **active_provider_config,
    }
    _validate_active_llm_config(final_llm_config)
    return final_llm_config


def _process_source_config(source_section: ConfigDict) -> ConfigDict:  # noqa: C901
    """Find the active language profile and merge it with common source settings."""
    # ... implementation unchanged ...
    if not isinstance(source_section, dict):
        raise ConfigError("'source' section must be dict.")
    language_profiles = source_section.get("language_profiles", [])
    active_profile: Optional[LanguageProfileDict] = None
    active_count = 0
    if not isinstance(language_profiles, list):
        raise ConfigError("'source.language_profiles' must be list.")
    for profile in language_profiles:
        if isinstance(profile, dict) and profile.get("is_active") is True:
            if not all(k in profile for k in ("language", "default_include_patterns")):
                raise ConfigError(f"Active language profile missing keys: {profile}")
            active_profile = profile
            active_count += 1
    if active_count == 0:
        raise ConfigError("No active language profile found.")
    if active_count > 1:
        raise ConfigError("Multiple active language profiles found.")
    if active_profile is None:
        raise ConfigError("Internal error: No active language profile identified.")
    final_source_config: ConfigDict = {
        "default_exclude_patterns": source_section.get("default_exclude_patterns", []),
        "max_file_size_bytes": source_section.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE),
        "use_relative_paths": source_section.get("use_relative_paths", True),
        **active_profile,
    }
    if active_profile.get("max_file_size_bytes") is not None:
        final_source_config["max_file_size_bytes"] = active_profile["max_file_size_bytes"]
    if active_profile.get("use_relative_paths") is not None:
        final_source_config["use_relative_paths"] = active_profile["use_relative_paths"]
    final_source_config.pop("is_active", None)
    return final_source_config


# --- Main load_config Function (Updated Defaults) ---
def load_config(config_path_str: str = "config.json") -> ConfigDict:
    """Load, validate, select active configs, apply defaults, return configuration.

    Args:
        config_path_str: Path to the configuration JSON file.

    Returns:
        A dictionary representing the fully validated and processed configuration.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ConfigError: If validation fails or required keys/profiles are missing/invalid.

    """
    config_path = Path(config_path_str)
    config_data = _read_config_file(config_path)
    # Validate against base schema BEFORE processing/adding defaults
    _validate_schema(config_data, config_path)

    # Process sections to select active profiles and merge settings
    # Use .get() with default {} in case top-level keys are missing (though schema requires them)
    config_data["llm"] = _process_llm_config(config_data.get("llm", {}))
    config_data["source"] = _process_source_config(config_data.get("source", {}))

    # Validate other sections AFTER processing LLM/Source
    _validate_github_token(config_data.get("github", {}))
    _ensure_cache_dir(config_data.get("cache", {}))

    # --- Apply defaults using schema defaults or constants ---
    # Use setdefault which modifies dict in-place and returns the value
    project_cfg = config_data.setdefault("project", CONFIG_SCHEMA["properties"]["project"]["default"])
    project_cfg.setdefault("default_name", None)  # Explicit default null

    output_cfg = config_data.setdefault("output", CONFIG_SCHEMA["properties"]["output"]["default"])
    output_cfg.setdefault("base_dir", DEFAULT_OUTPUT_DIR)
    output_cfg.setdefault("language", DEFAULT_LANGUAGE)
    # Set default for diagram_generation using its sub-schema default
    output_cfg.setdefault("diagram_generation", DIAGRAM_GENERATION_SCHEMA["default"])
    # Ensure nested defaults for sequence diagrams are also applied if diagram_generation was missing
    diag_gen_cfg = output_cfg["diagram_generation"]  # Get potentially newly added dict
    diag_gen_cfg.setdefault("separate_markup_file_generated", False)
    diag_gen_cfg.setdefault("format", "mermaid")
    diag_gen_cfg.setdefault("include_relationship_flowchart", True)
    diag_gen_cfg.setdefault("include_class_diagram", False)
    diag_gen_cfg.setdefault("include_package_diagram", False)
    seq_diag_cfg = diag_gen_cfg.setdefault(
        "include_sequence_diagrams", DIAGRAM_GENERATION_SCHEMA["properties"]["include_sequence_diagrams"]["default"]
    )
    seq_diag_cfg.setdefault("enabled", False)
    seq_diag_cfg.setdefault("max_diagrams", 5)
    seq_diag_cfg.setdefault("scenarios", [])

    logging_cfg = config_data.setdefault("logging", CONFIG_SCHEMA["properties"]["logging"]["default"])
    logging_cfg.setdefault("log_dir", DEFAULT_LOG_DIR)
    logging_cfg.setdefault("log_level", "INFO")

    cache_cfg = config_data.setdefault("cache", CONFIG_SCHEMA["properties"]["cache"]["default"])
    cache_cfg.setdefault("llm_cache_file", DEFAULT_CACHE_FILE)

    github_cfg = config_data.setdefault("github", CONFIG_SCHEMA["properties"]["github"]["default"])
    github_cfg.setdefault("token", None)

    return config_data


# End of src/sourcelens/config.py
