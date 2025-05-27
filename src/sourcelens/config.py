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

"""Load, validate, and process configuration for the SourceLens application.

This module handles reading settings from a JSON file, validating the structure
against a defined JSON schema, resolving secrets from environment variables,
selecting active LLM and language profiles, applying default values, and ensuring
necessary directories (cache, logs) exist. It provides a single, validated
configuration dictionary for the application. Includes detailed schema definitions
for all configurable sections.
"""

import copy
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional

from typing_extensions import TypeAlias

# Safe imports for optional dependencies
try:
    import jsonschema
    from jsonschema import validate as jsonschema_validate_func

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    jsonschema_validate_func = None  # type: ignore[assignment]
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
DEFAULT_SOURCE_INDEX_PARSER: Final[str] = "none"
DEFAULT_USER_AGENT: Final[str] = "SourceLensBot/0.1 (https://github.com/darijo2yahoocom/sourceLensAI)"
DEFAULT_WEB_PROCESSING_MODE: Final[str] = "minimalistic"


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
OUTPUT_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "base_dir": {"type": "string", "default": DEFAULT_OUTPUT_DIR},
        "language": {"type": "string", "default": DEFAULT_LANGUAGE},
        "diagram_generation": DIAGRAM_GENERATION_SCHEMA,
        "include_source_index": {
            "type": "boolean",
            "default": False,
            "description": "Globally controls if the source index (code_inventory.md) should be generated.",
        },
        "include_project_review": {
            "type": "boolean",
            "default": False,
            "description": "Globally controls if the AI-generated project review chapter should be generated.",
        },
    },
    "additionalProperties": False,
    "default": {
        "base_dir": DEFAULT_OUTPUT_DIR,
        "language": DEFAULT_LANGUAGE,
        "diagram_generation": DIAGRAM_GENERATION_SCHEMA["default"],
        "include_source_index": False,
        "include_project_review": False,
    },
}

WEB_CRAWLER_OPTIONS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "default_output_subdir_name": {"type": "string", "default": "crawled_web_content"},
        "max_depth_recursive": {"type": "integer", "minimum": 0, "default": 2},
        "user_agent": {"type": "string", "default": DEFAULT_USER_AGENT},
        "respect_robots_txt": {"type": "boolean", "default": True},
        "max_concurrent_requests": {"type": "integer", "minimum": 1, "default": 3},
        "processing_mode": {
            "type": "string",
            "enum": ["minimalistic", "llm_extended"],
            "default": DEFAULT_WEB_PROCESSING_MODE,
            "description": (
                "Controls how crawled web content is processed: "
                "'minimalistic' just saves Markdown files; "
                "'llm_extended' attempts to process them through the full LLM pipeline."
            ),
        },
    },
    "additionalProperties": False,
    "default": {
        "default_output_subdir_name": "crawled_web_content",
        "max_depth_recursive": 2,
        "user_agent": DEFAULT_USER_AGENT,
        "respect_robots_txt": True,
        "max_concurrent_requests": 3,
        "processing_mode": DEFAULT_WEB_PROCESSING_MODE,
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
        "output": OUTPUT_SCHEMA,
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
        "web_crawler_options": WEB_CRAWLER_OPTIONS_SCHEMA,
    },
    "required": ["source", "llm"],
    "additionalProperties": False,
}


class ConfigError(Exception):
    """Custom exception for configuration loading or validation errors."""


logger: logging.Logger = logging.getLogger(__name__)


class ConfigLoader:
    """Handles loading, validation, and processing of application configuration."""

    _config_data: ConfigDict
    _config_path: Path

    def __init__(self, config_path_str: str) -> None:
        """Initialize the ConfigLoader.

        Args:
            config_path_str (str): Path to the JSON configuration file.
        """
        self._config_path = Path(config_path_str).resolve()
        self._config_data = {}

    def _ensure_jsonschema_available(self) -> None:
        """Raise ImportError if jsonschema is not available."""
        if not JSONSCHEMA_AVAILABLE:
            raise ImportError("The 'jsonschema' library is required for config validation. Please install it.")

    def _read_config_file(self) -> None:
        """Read and parse the JSON configuration file into self._config_data.

        Raises:
            FileNotFoundError: If the configuration file is not found.
            ConfigError: If the file cannot be read or contains invalid JSON.
        """
        if not self._config_path.is_file():
            raise FileNotFoundError(f"Configuration file not found: '{self._config_path}'")
        try:
            with self._config_path.open(encoding="utf-8") as f:
                self._config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON syntax in '{self._config_path}': {e!s}") from e
        except OSError as e:
            raise ConfigError(f"Could not read configuration file '{self._config_path}': {e!s}") from e

    def _validate_schema(self) -> None:
        """Validate the loaded configuration data against the main JSON schema.

        Raises:
            ConfigError: If schema validation fails.
            RuntimeError: If jsonschema components are unexpectedly unavailable.
        """
        self._ensure_jsonschema_available()
        if (
            jsonschema_validate_func is None
            or jsonschema is None
            or not hasattr(jsonschema, "exceptions")
            or not hasattr(jsonschema.exceptions, "ValidationError")  # type: ignore[union-attr]
        ):
            raise RuntimeError("jsonschema components not available for validation despite initial check.")

        try:
            # Mypy is appeased by using the direct attribute access after the hasattr checks.
            validation_error_type: type[ValidationError] = jsonschema.exceptions.ValidationError  # type: ignore[union-attr]
            jsonschema_validate_func(instance=self._config_data, schema=CONFIG_SCHEMA)
            logger.debug("Configuration schema validation passed for %s.", self._config_path.name)
        except validation_error_type as e_val_err:  # type: ignore[misc]
            # The 'type: ignore[misc]' is for the broad exception type being caught,
            # which is dynamic based on jsonschema availability.
            path_str = " -> ".join(map(str, e_val_err.path)) if e_val_err.path else "root"
            err_msg = f"Config error in '{self._config_path.name}' at '{path_str}': {e_val_err.message}"
            logger.debug(
                "Schema validation failed. Instance: %s. Path: %s. Schema: %s",
                e_val_err.instance,
                path_str,
                e_val_err.schema,
            )
            raise ConfigError(err_msg) from e_val_err
        except Exception as e:  # Catch any other unexpected error during validation
            raise ConfigError(f"Unexpected error during schema validation: {e!s}") from e

    def _resolve_api_key(
        self, provider_name: Optional[str], current_key: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Resolve API key from config or environment variables.

        Args:
            provider_name (Optional[str]): The name of the LLM provider.
            current_key (Optional[str]): The API key currently set in the configuration.

        Returns:
            tuple[Optional[str], Optional[str]]: A tuple containing the resolved API key
                                                 (or None) and the name of the environment
                                                 variable checked (or None).
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
        if env_key_name and (api_key_from_env := os.environ.get(env_key_name)):
            logger.info("Loaded LLM API key for provider '%s' from env var '%s'.", provider_name, env_key_name)
            return api_key_from_env, env_key_name
        if env_key_name:
            logger.debug("Environment variable '%s' not set for provider '%s'.", env_key_name, provider_name)
        return None, env_key_name

    def _validate_local_llm_config(self, provider_cfg: ProviderConfigDict) -> None:
        """Validate config for local OpenAI-compatible LLMs.

        Args:
            provider_cfg (ProviderConfigDict): The configuration for the local LLM provider.

        Raises:
            ConfigError: If 'api_base_url' is missing or invalid.
        """
        provider: str = str(provider_cfg.get("provider", "local_llm"))
        api_base_url: Any = provider_cfg.get("api_base_url")
        if not api_base_url or not isinstance(api_base_url, str):
            raise ConfigError(f"For local provider '{provider}': Missing or invalid 'api_base_url'.")
        if provider_cfg.get("api_key"):
            logger.info("API key provided for local provider '%s'. Ensure this is supported.", provider)

    def _validate_vertexai_config(self, provider_cfg: ProviderConfigDict, checked_env_var: Optional[str]) -> None:
        """Validate config for Vertex AI.

        Updates `provider_cfg` with values from environment variables if not set.

        Args:
            provider_cfg (ProviderConfigDict): The configuration for the Vertex AI provider.
            checked_env_var (Optional[str]): The environment variable checked for API key/creds.

        Raises:
            ConfigError: If 'vertex_project' or 'vertex_location' are missing and not
                         found in environment variables.
        """
        provider: str = str(provider_cfg.get("provider", "vertexai"))
        api_key_or_creds_any: Any = provider_cfg.get("api_key")
        api_key_or_creds: Optional[str] = str(api_key_or_creds_any) if api_key_or_creds_any else None

        env_var_msg: str = ""
        if not api_key_or_creds:
            env_var_msg = f" or environment variable '{checked_env_var}'" if checked_env_var else ""
            logger.warning("Vertex AI: No API key/creds path in config%s. Using ADC.", env_var_msg)

        if not provider_cfg.get("vertex_project"):
            if proj_env := os.environ.get(ENV_VAR_GOOGLE_PROJECT):
                provider_cfg["vertex_project"] = proj_env
                logger.info("Loaded Vertex AI project '%s' from env var '%s'.", proj_env, ENV_VAR_GOOGLE_PROJECT)
            else:
                raise ConfigError(
                    f"Provider '{provider}': Missing 'vertex_project' and env var '{ENV_VAR_GOOGLE_PROJECT}'."
                )
        if not provider_cfg.get("vertex_location"):
            if loc_env := os.environ.get(ENV_VAR_GOOGLE_REGION):
                provider_cfg["vertex_location"] = loc_env
                logger.info("Loaded Vertex AI location '%s' from env var '%s'.", loc_env, ENV_VAR_GOOGLE_REGION)
            else:
                raise ConfigError(
                    f"Provider '{provider}': Missing 'vertex_location' and env var '{ENV_VAR_GOOGLE_REGION}'."
                )

    def _validate_standard_cloud_config(self, provider_cfg: ProviderConfigDict, checked_env_var: Optional[str]) -> None:
        """Validate config for standard cloud LLMs needing an API key.

        Args:
            provider_cfg (ProviderConfigDict): Configuration for the cloud LLM provider.
            checked_env_var (Optional[str]): The environment variable checked for the API key.

        Raises:
            ConfigError: If 'api_key' is missing.
        """
        provider = str(provider_cfg.get("provider", "Unknown Cloud Provider"))
        if not provider_cfg.get("api_key"):
            env_msg = f" and env var '{checked_env_var}' was not set" if checked_env_var else ""
            raise ConfigError(f"Cloud provider '{provider}': Missing 'api_key' in config{env_msg}.")
        if api_base_url := provider_cfg.get("api_base_url"):
            logger.warning(
                "Cloud provider '%s': 'api_base_url' ('%s') is set but likely unused.", provider, api_base_url
            )

    def _validate_active_llm_config(self, active_llm_cfg: ProviderConfigDict) -> None:
        """Validate the chosen active LLM provider's configuration.

        Args:
            active_llm_cfg (ProviderConfigDict): The configuration for the active LLM.

        Raises:
            ValueError: If 'provider' key is missing or not a string.
            ConfigError: For other configuration issues specific to the provider type.
        """
        provider_any: Any = active_llm_cfg.get("provider")
        if not isinstance(provider_any, str):
            raise ValueError("Active LLM provider config missing 'provider' name or it's not a string.")
        provider: str = provider_any
        is_local: bool = bool(active_llm_cfg.get("is_local_llm", False))
        current_api_key: Optional[str] = str(active_llm_cfg.get("api_key")) if active_llm_cfg.get("api_key") else None
        checked_env_var: Optional[str] = None

        logger.debug("Validating active LLM provider config: %s", provider)
        if not is_local:
            resolved_key, checked_env_var = self._resolve_api_key(provider, current_api_key)
            active_llm_cfg["api_key"] = resolved_key

        if is_local:
            self._validate_local_llm_config(active_llm_cfg)
        elif provider == "vertexai":
            self._validate_vertexai_config(active_llm_cfg, checked_env_var)
        else:
            self._validate_standard_cloud_config(active_llm_cfg, checked_env_var)
        logger.debug("Active LLM provider config validation successful for: %s", provider)

    def _validate_github_token(self) -> None:
        """Validate GitHub token presence, updating `self._config_data`."""
        github_cfg_any: Any = self._config_data.get("github", {})
        github_cfg: ConfigDict = github_cfg_any if isinstance(github_cfg_any, dict) else {}
        self._config_data["github"] = github_cfg

        if github_cfg.get("token") is None:
            logger.debug("GitHub token not in config. Checking env var '%s'.", ENV_VAR_GITHUB_TOKEN)
            if env_github_token := os.environ.get(ENV_VAR_GITHUB_TOKEN):
                github_cfg["token"] = env_github_token
                logger.info("Loaded GitHub token from env var '%s'.", ENV_VAR_GITHUB_TOKEN)
            else:
                logger.warning(
                    "No GitHub token in config or env var '%s'. Private repo access may be affected.",
                    ENV_VAR_GITHUB_TOKEN,
                )
        else:
            logger.debug("GitHub token found in configuration file.")

    def _ensure_directory_exists(self, dir_path_str: Optional[str], dir_purpose: str, default_path: str) -> None:
        """Ensure a directory exists, creating it if necessary.

        Args:
            dir_path_str (Optional[str]): The path string for the directory from config.
            dir_purpose (str): A description of the directory's purpose (for logging).
            default_path (str): The default path to use if `dir_path_str` is None or empty.
        """
        path_to_use_str = dir_path_str if isinstance(dir_path_str, str) and dir_path_str.strip() else default_path
        if not path_to_use_str:
            logger.error(
                "Cannot ensure %s directory: No valid path provided (path was '%s').", dir_purpose, path_to_use_str
            )
            return
        try:
            path_to_use = Path(path_to_use_str)
            target_for_mkdir = path_to_use.parent if dir_purpose == "LLM cache" and path_to_use.suffix else path_to_use

            if target_for_mkdir != Path():
                target_for_mkdir.mkdir(parents=True, exist_ok=True)
                logger.debug("Ensured %s directory structure exists for: %s", dir_purpose, target_for_mkdir.resolve())
        except OSError as e:
            logger.error(
                "Could not create/ensure %s directory for '%s': %s", dir_purpose, path_to_use_str, e, exc_info=True
            )
        except Exception as e_unexp:
            logger.error(
                "Unexpected error ensuring %s dir for '%s': %s", dir_purpose, path_to_use_str, e_unexp, exc_info=True
            )

    def _apply_defaults_and_validate_sections(self) -> None:
        """Apply default values from schema and run specific validations.

        Ensures top-level sections exist, applies their defaults if defined in schema,
        and handles directory creation for logging and caching.
        """
        cfg = self._config_data

        for section_key, section_schema in CONFIG_SCHEMA["properties"].items():
            if section_key not in cfg and "default" in section_schema:
                cfg[section_key] = copy.deepcopy(section_schema["default"])
            elif section_key not in cfg and section_schema.get("type") == "object":
                cfg[section_key] = {}

        project_s: ConfigDict = cfg.get("project", {})  # type: ignore[assignment]
        project_s.setdefault("default_name", CONFIG_SCHEMA["properties"]["project"]["default"]["default_name"])  # type: ignore[index]

        output_s: ConfigDict = cfg.get("output", {})  # type: ignore[assignment]
        output_s.setdefault("base_dir", OUTPUT_SCHEMA["default"]["base_dir"])  # type: ignore[index]
        output_s.setdefault("language", OUTPUT_SCHEMA["default"]["language"])  # type: ignore[index]
        output_s.setdefault("include_source_index", OUTPUT_SCHEMA["default"]["include_source_index"])  # type: ignore[index]
        output_s.setdefault("include_project_review", OUTPUT_SCHEMA["default"]["include_project_review"])  # type: ignore[index]

        diag_gen_s: ConfigDict = output_s.get("diagram_generation", {})  # type: ignore[assignment]
        if not isinstance(diag_gen_s, dict) or not diag_gen_s:
            diag_gen_s = copy.deepcopy(DIAGRAM_GENERATION_SCHEMA["default"])  # type: ignore[index]
        output_s["diagram_generation"] = diag_gen_s
        diag_gen_s.setdefault("format", DIAGRAM_GENERATION_SCHEMA["default"]["format"])  # type: ignore[index]

        logging_s: ConfigDict = cfg.get("logging", {})  # type: ignore[assignment]
        logging_s.setdefault("log_dir", CONFIG_SCHEMA["properties"]["logging"]["default"]["log_dir"])  # type: ignore[index]
        logging_s.setdefault("log_level", CONFIG_SCHEMA["properties"]["logging"]["default"]["log_level"])  # type: ignore[index]
        self._ensure_directory_exists(str(logging_s.get("log_dir")), "logging", DEFAULT_LOG_DIR)

        cache_s: ConfigDict = cfg.get("cache", {})  # type: ignore[assignment]
        cache_s.setdefault("llm_cache_file", CONFIG_SCHEMA["properties"]["cache"]["default"]["llm_cache_file"])  # type: ignore[index]
        self._ensure_directory_exists(str(cache_s.get("llm_cache_file")), "LLM cache", DEFAULT_CACHE_FILE)

        self._validate_github_token()

        web_crawler_s: ConfigDict = cfg.get("web_crawler_options", {})  # type: ignore[assignment]
        default_web_opts: dict[str, Any] = WEB_CRAWLER_OPTIONS_SCHEMA.get("default", {})  # type: ignore[assignment]
        for key, default_val in default_web_opts.items():
            web_crawler_s.setdefault(key, default_val)
        cfg["web_crawler_options"] = web_crawler_s

    def _process_llm_config(self) -> None:
        """Process the LLM section, select active provider, and validate.

        Raises:
            ConfigError: If LLM configuration is missing, invalid, or no active provider found.
        """
        llm_section_any: Any = self._config_data.get("llm", {})
        llm_section: ConfigDict = llm_section_any if isinstance(llm_section_any, dict) else {}
        if not llm_section:
            raise ConfigError("Config error: 'llm' section is missing or not a dictionary.")

        provider_configs_any: Any = llm_section.get("providers", [])
        provider_configs: list[Any] = provider_configs_any if isinstance(provider_configs_any, list) else []
        if not provider_configs:
            raise ConfigError("Config error: 'llm.providers' must be a non-empty list.")

        active_provider_configs = [
            p_cfg for p_cfg in provider_configs if isinstance(p_cfg, dict) and p_cfg.get("is_active") is True
        ]
        if not active_provider_configs:
            raise ConfigError("No active LLM provider in 'llm.providers'. Set one 'is_active: true'.")
        if len(active_provider_configs) > 1:
            raise ConfigError("Multiple active LLM providers. Set only one 'is_active: true'.")

        active_provider_config: ProviderConfigDict = active_provider_configs[0]
        if not all(k in active_provider_config for k in ("provider", "model", "is_local_llm")):
            raise ConfigError(f"Active LLM provider config missing required keys: {active_provider_config}")

        self._validate_active_llm_config(active_provider_config)

        final_llm_config: ConfigDict = {
            "max_retries": llm_section.get("max_retries", DEFAULT_LLM_RETRIES),
            "retry_wait_seconds": llm_section.get("retry_wait_seconds", DEFAULT_LLM_WAIT),
            "use_cache": llm_section.get("use_cache", True),
            **active_provider_config,
        }
        self._config_data["llm"] = final_llm_config

    def _find_active_language_profile(self) -> LanguageProfileDict:
        """Find and return the active language profile.

        Returns:
            LanguageProfileDict: The active language profile.

        Raises:
            ConfigError: If 'source' section or 'language_profiles' are missing/invalid,
                         or if no active profile is found or multiple are active.
        """
        source_section_any: Any = self._config_data.get("source", {})
        source_section: ConfigDict = source_section_any if isinstance(source_section_any, dict) else {}
        if not source_section:
            raise ConfigError("Config error: 'source' section missing or not a dictionary.")

        lang_profiles_any: Any = source_section.get("language_profiles", [])
        lang_profiles: list[Any] = lang_profiles_any if isinstance(lang_profiles_any, list) else []
        if not lang_profiles:
            raise ConfigError("Config error: 'source.language_profiles' must be a non-empty list.")

        active_profiles = [p for p in lang_profiles if isinstance(p, dict) and p.get("is_active") is True]
        if not active_profiles:
            raise ConfigError("No active language profile in 'source.language_profiles'.")
        if len(active_profiles) > 1:
            raise ConfigError("Multiple active language profiles. Set only one 'is_active: true'.")

        active_profile: LanguageProfileDict = active_profiles[0]
        req_keys = ("language", "default_include_patterns", "source_index_parser")
        if not all(k in active_profile for k in req_keys):
            missing = [k for k in req_keys if k not in active_profile]
            raise ConfigError(f"Active language profile missing keys: {', '.join(missing)}. Profile: {active_profile}")
        return active_profile

    def _process_source_config(self) -> None:
        """Process the source section, select active language profile, and apply overrides.

        Raises:
            ConfigError: If 'source' section is missing or other processing errors occur.
        """
        source_section_any: Any = self._config_data.get("source", {})
        source_section: ConfigDict = source_section_any if isinstance(source_section_any, dict) else {}
        if not source_section:
            raise ConfigError("Config error: 'source' section is missing or not a dictionary.")

        active_profile = self._find_active_language_profile()

        final_source_config: ConfigDict = {
            "default_exclude_patterns": source_section.get("default_exclude_patterns", []),
            "max_file_size_bytes": source_section.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE),
            "use_relative_paths": source_section.get("use_relative_paths", True),
        }
        final_source_config.update(active_profile)

        if "max_file_size_bytes" in active_profile:
            final_source_config["max_file_size_bytes"] = active_profile["max_file_size_bytes"]
        if "use_relative_paths" in active_profile:
            final_source_config["use_relative_paths"] = active_profile["use_relative_paths"]

        final_source_config.pop("is_active", None)
        self._config_data["source"] = final_source_config
        logger.debug("Processed source config using active lang profile: %s", active_profile.get("language"))

    def process(self) -> ConfigDict:
        """Load, validate, and process the configuration.

        Returns:
            ConfigDict: The fully processed and validated configuration dictionary.

        Raises:
            ConfigError: If any step of configuration loading or processing fails.
            FileNotFoundError: If the configuration file is not found.
            ImportError: If jsonschema is required but not installed.
        """
        logger.info("Loading configuration from: %s", self._config_path)
        self._read_config_file()
        self._validate_schema()
        self._apply_defaults_and_validate_sections()
        self._process_llm_config()
        self._process_source_config()

        logger.info("Configuration loaded and processed successfully.")
        if logger.isEnabledFor(logging.DEBUG):
            try:
                log_config_copy = json.loads(json.dumps(self._config_data))
                if "llm" in log_config_copy and isinstance(log_config_copy["llm"], dict):
                    log_config_copy["llm"]["api_key"] = "***REDACTED***"
                if "github" in log_config_copy and isinstance(log_config_copy["github"], dict):
                    log_config_copy["github"]["token"] = "***REDACTED***"
                logger.debug("Final processed config data: %s", json.dumps(log_config_copy, indent=2))
            except (TypeError, ValueError) as dump_error:
                logger.debug("Could not serialize final config for debug logging: %s", dump_error)
        return self._config_data


def load_config(config_path_str: str = "config.json") -> ConfigDict:
    """Load, validate, process, and return the application configuration.

    This function instantiates and uses `ConfigLoader` to perform the work.

    Args:
        config_path_str (str): The path string to the configuration JSON file.
                               Defaults to "config.json".

    Returns:
        ConfigDict: The fully processed and validated configuration dictionary.

    Raises:
        ConfigError: If any step of configuration loading or processing fails.
        FileNotFoundError: If the configuration file is not found.
        ImportError: If jsonschema is required but not installed.
    """
    loader = ConfigLoader(config_path_str)
    return loader.process()


# End of src/sourcelens/config.py
