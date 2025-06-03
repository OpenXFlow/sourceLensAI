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

This module handles loading a global configuration and merging it with
flow-specific default configurations and CLI overrides.
"""

import copy
import json
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Final, Optional, cast

from typing_extensions import TypeAlias

JSONSCHEMA_AVAILABLE = False
jsonschema_validate_func: Optional[Callable[..., None]] = None
JsonSchemaValidationError_type: Optional[type[Exception]] = None
jsonschema_exceptions_module: Optional[ModuleType] = None
jsonschema_module: Optional[ModuleType] = None

try:
    import jsonschema as imported_jsonschema_module_for_try
    from jsonschema import validate as jsonschema_validate_func_real
    from jsonschema.exceptions import ValidationError as JsonSchemaValidationError_real

    jsonschema_module = imported_jsonschema_module_for_try
    jsonschema_validate_func = jsonschema_validate_func_real
    JsonSchemaValidationError_type = JsonSchemaValidationError_real
    # Priradíme modul exceptions do našej premennej
    if hasattr(jsonschema_module, "exceptions"):
        jsonschema_exceptions_module = jsonschema_module.exceptions
    JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    # Všetky zostanú None, ako boli inicializované
    pass

if TYPE_CHECKING:  # pragma: no cover
    import argparse

    if JSONSCHEMA_AVAILABLE and JsonSchemaValidationError_type is not None:
        pass

ConfigDict: TypeAlias = dict[str, Any]
LlmProfileDict: TypeAlias = dict[str, Any]
LanguageProfileDict: TypeAlias = dict[str, Any]
CommonOutputSettingsDict: TypeAlias = dict[str, Any]
LoggingConfigDict: TypeAlias = dict[str, Any]
CacheSettingsDict: TypeAlias = dict[str, Any]
LlmDefaultOptionsDict: TypeAlias = dict[str, Any]
FlowSourceOptionsDict: TypeAlias = dict[str, Any]
FlowDiagramGenerationDict: TypeAlias = dict[str, Any]
FlowOutputOptionsDict: TypeAlias = dict[str, Any]
FlowCrawlerOptionsDict: TypeAlias = dict[str, Any]

AUTO_DETECT_OUTPUT_NAME: Final[str] = "auto-generated"
DEFAULT_MAIN_OUTPUT_DIR: Final[str] = "output"
DEFAULT_GENERATED_TEXT_LANGUAGE: Final[str] = "english"
DEFAULT_LOG_DIR: Final[str] = "logs"
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_USE_LLM_CACHE: Final[bool] = True
DEFAULT_LLM_CACHE_FILE: Final[str] = ".cache/llm_cache.json"
DEFAULT_LLM_MAX_RETRIES: Final[int] = 3
DEFAULT_LLM_RETRY_WAIT_SECONDS: Final[int] = 10
DEFAULT_GITHUB_TOKEN_ENV_VAR: Final[str] = "GITHUB_TOKEN"
DEFAULT_CODE_ANALYSIS_ENABLED: Final[bool] = True
DEFAULT_CODE_MAX_FILE_SIZE_BYTES: Final[int] = 150000
DEFAULT_CODE_USE_RELATIVE_PATHS: Final[bool] = True
DEFAULT_CODE_DIAGRAMS_ENABLED: Final[bool] = True
DEFAULT_CODE_DIAGRAM_FORMAT: Final[str] = "mermaid"
DEFAULT_CODE_INCLUDE_FILE_STRUCTURE_DIAGRAM: Final[bool] = True
DEFAULT_CODE_SEQ_DIAGRAMS_ENABLED: Final[bool] = True
DEFAULT_CODE_SEQ_DIAGRAMS_MAX: Final[int] = 5
DEFAULT_CODE_INCLUDE_SOURCE_INDEX: Final[bool] = True
DEFAULT_CODE_INCLUDE_PROJECT_REVIEW: Final[bool] = True
DEFAULT_WEB_ANALYSIS_ENABLED: Final[bool] = True
DEFAULT_WEB_OUTPUT_SUBDIR_NAME: Final[str] = "crawled_web_content"
DEFAULT_WEB_PROCESSING_MODE: Final[str] = "minimalistic"
DEFAULT_WEB_MAX_DEPTH_RECURSIVE: Final[int] = 2
DEFAULT_WEB_USER_AGENT: Final[str] = "SourceLensBot/0.1 (https://github.com/openXFlow/sourceLensAI)"
DEFAULT_WEB_RESPECT_ROBOTS: Final[bool] = True
DEFAULT_WEB_MAX_CONCURRENT_REQUESTS: Final[int] = 3
DEFAULT_WEB_PAGE_TIMEOUT_MS: Final[int] = 30000
DEFAULT_WEB_WORD_COUNT_THRESHOLD_MARKDOWN: Final[int] = 50
DEFAULT_WEB_INCLUDE_CONTENT_INVENTORY: Final[bool] = True
DEFAULT_WEB_INCLUDE_CONTENT_REVIEW: Final[bool] = True
DEFAULT_LANGUAGE_PARSER_TYPE: Final[str] = "llm"
ENV_VAR_GEMINI_KEY: Final[str] = "GEMINI_API_KEY"
ENV_VAR_ANTHROPIC_KEY: Final[str] = "ANTHROPIC_API_KEY"
ENV_VAR_OPENAI_KEY: Final[str] = "OPENAI_API_KEY"
ENV_VAR_PERPLEXITY_KEY: Final[str] = "PERPLEXITY_API_KEY"
ENV_VAR_VERTEX_CREDS: Final[str] = "GOOGLE_APPLICATION_CREDENTIALS"
ENV_VAR_GOOGLE_PROJECT: Final[str] = "GOOGLE_CLOUD_PROJECT"
ENV_VAR_GOOGLE_REGION: Final[str] = "GOOGLE_CLOUD_REGION"

COMMON_OUTPUT_SETTINGS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "default_output_name": {"type": ["string", "null"], "default": AUTO_DETECT_OUTPUT_NAME},
        "main_output_directory": {"type": "string", "default": DEFAULT_MAIN_OUTPUT_DIR},
        "generated_text_language": {"type": "string", "default": DEFAULT_GENERATED_TEXT_LANGUAGE},
    },
    "additionalProperties": False,
    "default": {
        "default_output_name": AUTO_DETECT_OUTPUT_NAME,
        "main_output_directory": DEFAULT_MAIN_OUTPUT_DIR,
        "generated_text_language": DEFAULT_GENERATED_TEXT_LANGUAGE,
    },
}
LOGGING_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "log_dir": {"type": "string", "default": DEFAULT_LOG_DIR},
        "log_level": {
            "type": "string",
            "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "default": DEFAULT_LOG_LEVEL,
        },
        "log_file": {"type": ["string", "null"], "default": None},
    },
    "additionalProperties": False,
    "default": {"log_dir": DEFAULT_LOG_DIR, "log_level": DEFAULT_LOG_LEVEL, "log_file": None},
}
CACHE_SETTINGS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "use_llm_cache": {"type": "boolean", "default": DEFAULT_USE_LLM_CACHE},
        "llm_cache_file": {"type": "string", "default": DEFAULT_LLM_CACHE_FILE},
    },
    "additionalProperties": False,
    "default": {"use_llm_cache": DEFAULT_USE_LLM_CACHE, "llm_cache_file": DEFAULT_LLM_CACHE_FILE},
}
LLM_DEFAULT_OPTIONS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "max_retries": {"type": "integer", "minimum": 0, "default": DEFAULT_LLM_MAX_RETRIES},
        "retry_wait_seconds": {"type": "integer", "minimum": 0, "default": DEFAULT_LLM_RETRY_WAIT_SECONDS},
    },
    "additionalProperties": False,
    "default": {"max_retries": DEFAULT_LLM_MAX_RETRIES, "retry_wait_seconds": DEFAULT_LLM_RETRY_WAIT_SECONDS},
}
COMMON_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "common_output_settings": COMMON_OUTPUT_SETTINGS_SCHEMA,
        "logging": LOGGING_SCHEMA,
        "cache_settings": CACHE_SETTINGS_SCHEMA,
        "llm_default_options": LLM_DEFAULT_OPTIONS_SCHEMA,
    },
    "required": ["common_output_settings", "logging", "cache_settings", "llm_default_options"],
    "additionalProperties": False,
}
CODE_ANALYSIS_SOURCE_OPTIONS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "max_file_size_bytes": {"type": "integer", "minimum": 0, "default": DEFAULT_CODE_MAX_FILE_SIZE_BYTES},
        "use_relative_paths": {"type": "boolean", "default": DEFAULT_CODE_USE_RELATIVE_PATHS},
        "default_exclude_patterns": {"type": "array", "items": {"type": "string"}, "default": []},
    },
    "additionalProperties": True,
    "default": {
        "max_file_size_bytes": DEFAULT_CODE_MAX_FILE_SIZE_BYTES,
        "use_relative_paths": DEFAULT_CODE_USE_RELATIVE_PATHS,
        "default_exclude_patterns": [],
    },
}
CODE_ANALYSIS_DIAGRAM_GENERATION_SEQUENCE_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "default": DEFAULT_CODE_SEQ_DIAGRAMS_ENABLED},
        "max_diagrams_to_generate": {"type": "integer", "minimum": 0, "default": DEFAULT_CODE_SEQ_DIAGRAMS_MAX},
    },
    "additionalProperties": False,
    "default": {
        "enabled": DEFAULT_CODE_SEQ_DIAGRAMS_ENABLED,
        "max_diagrams_to_generate": DEFAULT_CODE_SEQ_DIAGRAMS_MAX,
    },
}
CODE_ANALYSIS_DIAGRAM_GENERATION_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "default": DEFAULT_CODE_DIAGRAMS_ENABLED},
        "format": {"type": "string", "enum": ["mermaid"], "default": DEFAULT_CODE_DIAGRAM_FORMAT},
        "include_relationship_flowchart": {"type": "boolean", "default": True},
        "include_class_diagram": {"type": "boolean", "default": True},
        "include_package_diagram": {"type": "boolean", "default": True},
        "include_file_structure_diagram": {"type": "boolean", "default": DEFAULT_CODE_INCLUDE_FILE_STRUCTURE_DIAGRAM},
        "sequence_diagrams": CODE_ANALYSIS_DIAGRAM_GENERATION_SEQUENCE_SCHEMA,
    },
    "additionalProperties": False,
    "default": {
        "enabled": DEFAULT_CODE_DIAGRAMS_ENABLED,
        "format": DEFAULT_CODE_DIAGRAM_FORMAT,
        "include_relationship_flowchart": True,
        "include_class_diagram": True,
        "include_package_diagram": True,
        "include_file_structure_diagram": DEFAULT_CODE_INCLUDE_FILE_STRUCTURE_DIAGRAM,
        "sequence_diagrams": CODE_ANALYSIS_DIAGRAM_GENERATION_SEQUENCE_SCHEMA["default"],
    },
}
CODE_ANALYSIS_OUTPUT_OPTIONS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "include_source_index": {"type": "boolean", "default": DEFAULT_CODE_INCLUDE_SOURCE_INDEX},
        "include_project_review": {"type": "boolean", "default": DEFAULT_CODE_INCLUDE_PROJECT_REVIEW},
    },
    "additionalProperties": False,
    "default": {
        "include_source_index": DEFAULT_CODE_INCLUDE_SOURCE_INDEX,
        "include_project_review": DEFAULT_CODE_INCLUDE_PROJECT_REVIEW,
    },
}
CODE_ANALYSIS_GLOBAL_OVERRIDES_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "github_token_env_var": {"type": ["string", "null"]},
        "github_token": {"type": ["string", "null"]},
        "active_language_profile_id": {"type": "string"},
        "active_llm_provider_id": {"type": "string"},
        "source_config": {"type": "object"},
        "source_options": CODE_ANALYSIS_SOURCE_OPTIONS_SCHEMA,
        "diagram_generation": CODE_ANALYSIS_DIAGRAM_GENERATION_SCHEMA,
        "output_options": CODE_ANALYSIS_OUTPUT_OPTIONS_SCHEMA,
    },
    "additionalProperties": True,
}
WEB_ANALYSIS_CRAWLER_OPTIONS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "default_output_subdir_name": {"type": "string", "default": DEFAULT_WEB_OUTPUT_SUBDIR_NAME},
        "processing_mode": {
            "type": "string",
            "enum": ["minimalistic", "llm_extended"],
            "default": DEFAULT_WEB_PROCESSING_MODE,
        },
        "max_depth_recursive": {"type": "integer", "minimum": 0, "default": DEFAULT_WEB_MAX_DEPTH_RECURSIVE},
        "user_agent": {"type": "string", "default": DEFAULT_WEB_USER_AGENT},
        "respect_robots_txt": {"type": "boolean", "default": DEFAULT_WEB_RESPECT_ROBOTS},
        "max_concurrent_requests": {"type": "integer", "minimum": 1, "default": DEFAULT_WEB_MAX_CONCURRENT_REQUESTS},
        "default_page_timeout_ms": {"type": "integer", "minimum": 0, "default": DEFAULT_WEB_PAGE_TIMEOUT_MS},
        "word_count_threshold_for_markdown": {
            "type": "integer",
            "minimum": 0,
            "default": DEFAULT_WEB_WORD_COUNT_THRESHOLD_MARKDOWN,
        },
    },
    "additionalProperties": False,
    "default": {
        "default_output_subdir_name": DEFAULT_WEB_OUTPUT_SUBDIR_NAME,
        "processing_mode": DEFAULT_WEB_PROCESSING_MODE,
        "max_depth_recursive": DEFAULT_WEB_MAX_DEPTH_RECURSIVE,
        "user_agent": DEFAULT_WEB_USER_AGENT,
        "respect_robots_txt": DEFAULT_WEB_RESPECT_ROBOTS,
        "max_concurrent_requests": DEFAULT_WEB_MAX_CONCURRENT_REQUESTS,
        "default_page_timeout_ms": DEFAULT_WEB_PAGE_TIMEOUT_MS,
        "word_count_threshold_for_markdown": DEFAULT_WEB_WORD_COUNT_THRESHOLD_MARKDOWN,
    },
}
WEB_ANALYSIS_OUTPUT_OPTIONS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "include_content_inventory": {"type": "boolean", "default": DEFAULT_WEB_INCLUDE_CONTENT_INVENTORY},
        "include_content_review": {"type": "boolean", "default": DEFAULT_WEB_INCLUDE_CONTENT_REVIEW},
    },
    "additionalProperties": False,
    "default": {
        "include_content_inventory": DEFAULT_WEB_INCLUDE_CONTENT_INVENTORY,
        "include_content_review": DEFAULT_WEB_INCLUDE_CONTENT_REVIEW,
    },
}
WEB_ANALYSIS_GLOBAL_OVERRIDES_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "active_llm_provider_id": {"type": "string"},
        "crawler_options": WEB_ANALYSIS_CRAWLER_OPTIONS_SCHEMA,
        "output_options": WEB_ANALYSIS_OUTPUT_OPTIONS_SCHEMA,
    },
    "additionalProperties": True,
}
LANGUAGE_PROFILE_SCHEMA_ITEM: ConfigDict = {
    "type": "object",
    "properties": {
        "profile_id": {"type": "string"},
        "language_name_for_llm": {"type": "string"},
        "parser_type": {"type": "string", "enum": ["ast", "llm", "none"]},
        "include_patterns": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["profile_id", "language_name_for_llm", "parser_type"],
    "additionalProperties": False,
}
LLM_PROFILE_SCHEMA_ITEM: ConfigDict = {
    "type": "object",
    "properties": {
        "provider_id": {"type": "string"},
        "is_local_llm": {"type": "boolean"},
        "provider": {"type": "string"},
        "model": {"type": "string"},
        "api_key_env_var": {"type": ["string", "null"]},
        "api_key": {"type": ["string", "null"]},
        "api_base_url": {"type": ["string", "null"]},
        "vertex_project_env_var": {"type": ["string", "null"]},
        "vertex_location_env_var": {"type": ["string", "null"]},
        "vertex_project": {"type": ["string", "null"]},
        "vertex_location": {"type": ["string", "null"]},
    },
    "required": ["provider_id", "is_local_llm", "provider", "model"],
    "additionalProperties": False,
}
PROFILES_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "language_profiles": {"type": "array", "minItems": 1, "items": LANGUAGE_PROFILE_SCHEMA_ITEM},
        "llm_profiles": {"type": "array", "minItems": 1, "items": LLM_PROFILE_SCHEMA_ITEM},
    },
    "required": ["language_profiles", "llm_profiles"],
    "additionalProperties": False,
}
GLOBAL_ROOT_CONFIG_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "common": COMMON_SCHEMA,
        "profiles": PROFILES_SCHEMA,
        "FL01_code_analysis": CODE_ANALYSIS_GLOBAL_OVERRIDES_SCHEMA,
        "FL02_web_crawling": WEB_ANALYSIS_GLOBAL_OVERRIDES_SCHEMA,
    },
    "required": ["common", "profiles"],
    "additionalProperties": True,
}


class ConfigError(Exception):
    """Custom exception for configuration loading or validation errors."""


module_logger: logging.Logger = logging.getLogger(__name__)


class ConfigLoader:
    """Handles loading, validation, and processing of application configurations."""

    _global_config_data: ConfigDict
    _global_config_path: Path
    _logger: logging.Logger

    def __init__(self, global_config_path_str: str) -> None:
        """Initialize ConfigLoader with the path to the global configuration file.

        Args:
            global_config_path_str: Path to the main global JSON configuration file.
        """
        self._global_config_path = Path(global_config_path_str).resolve()
        self._global_config_data = {}
        self._logger = logging.getLogger(self.__class__.__name__)
        self._load_and_validate_global_config()

    def _ensure_jsonschema_available(self) -> None:  # pragma: no cover
        """Check if jsonschema library is available and raise ImportError if not."""
        if not JSONSCHEMA_AVAILABLE:
            raise ImportError("The 'jsonschema' library is required for schema validation. Please install it.")

    def _read_json_file(self, file_path: Path) -> ConfigDict:
        """Read and parse a JSON configuration file.

        Args:
            file_path: Path object pointing to the JSON file.

        Returns:
            ConfigDict: The loaded configuration as a dictionary.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ConfigError: If the file cannot be read, is not valid JSON,
                         or the root JSON structure is not a dictionary.
        """
        if not file_path.is_file():
            raise FileNotFoundError(f"Configuration file not found: '{file_path}'")
        try:
            with file_path.open(encoding="utf-8") as f:
                loaded_data: Any = json.load(f)
                if not isinstance(loaded_data, dict):
                    msg = f"Configuration in '{file_path}' is not a valid JSON object (dictionary)."
                    raise ConfigError(msg)
                return cast(ConfigDict, loaded_data)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON syntax in '{file_path}': {e!s}") from e
        except OSError as e:
            raise ConfigError(f"Could not read configuration file '{file_path}': {e!s}") from e

    def _validate_against_schema(self, instance: ConfigDict, schema: ConfigDict, file_description: str) -> None:
        """Validate a configuration instance against a given JSON schema.

        Args:
            instance: The configuration data (dictionary) to validate.
            schema: The JSON schema (dictionary) to validate against.
            file_description: A descriptive string for the configuration being validated (for logging).

        Raises:
            ImportError: If 'jsonschema' library is not installed.
            ConfigError: If schema validation fails or an unexpected error occurs during validation.
        """
        self._ensure_jsonschema_available()
        # Check that all necessary jsonschema components are not None before use
        if not (
            jsonschema_validate_func is not None
            and jsonschema_exceptions_module is not None  # Check the module itself
            and JsonSchemaValidationError_type is not None
            # Additionally check if ValidationError can be accessed from the exceptions module
            and hasattr(jsonschema_exceptions_module, "ValidationError")  # This was the problematic line
        ):  # pragma: no cover
            raise RuntimeError("jsonschema components unexpectedly unavailable after import check.")

        try:
            jsonschema_validate_func(instance=instance, schema=schema)
            self._logger.debug("Schema validation passed for %s.", file_description)
        except JsonSchemaValidationError_type as e_val_err:
            path_list = getattr(e_val_err, "path", [])
            path_str = " -> ".join(map(str, path_list)) if path_list else "root"
            message_str = getattr(e_val_err, "message", str(e_val_err))
            err_msg = f"Config error in {file_description} at '{path_str}': {message_str}"
            instance_val = getattr(e_val_err, "instance", None)
            validator_val = getattr(e_val_err, "validator", "N/A")
            schema_path_list = getattr(e_val_err, "schema_path", [])
            schema_path_str = " -> ".join(map(str, schema_path_list))
            self._logger.debug(
                "Schema validation failed for %s. Instance: %s. Path: %s. Validator: %s. Schema path: %s",
                file_description,
                instance_val,
                path_str,
                validator_val,
                schema_path_str,
            )
            raise ConfigError(err_msg) from e_val_err
        except Exception as e:  # pragma: no cover
            log_msg_l1 = f"Unexpected error during schema validation for {file_description}: "
            log_msg_l2 = f"{e!s}"  # Shorter line
            self._logger.error(log_msg_l1 + log_msg_l2, exc_info=True)
            raise ConfigError(log_msg_l1 + log_msg_l2) from e

    def _load_and_validate_global_config(self) -> None:
        """Load and validate the main global configuration file against its schema."""
        self._logger.info("Loading global configuration from: %s", self._global_config_path)
        self._global_config_data = self._read_json_file(self._global_config_path)
        self._validate_against_schema(
            self._global_config_data, GLOBAL_ROOT_CONFIG_SCHEMA, f"global config '{self._global_config_path.name}'"
        )
        self._apply_defaults_to_common_section(self._global_config_data)

    def _apply_defaults_to_common_section(self, config_dict: ConfigDict) -> None:
        """Apply default values to the 'common' section if keys are missing.

        Args:
            config_dict: The configuration dictionary (modified in-place).
        """
        common_cfg: ConfigDict = config_dict.setdefault("common", {})
        common_schema_props = COMMON_SCHEMA.get("properties", {})

        for sub_key, sub_schema in common_schema_props.items():
            sub_block = common_cfg.setdefault(sub_key, {})
            sub_defaults = sub_schema.get("default", {})
            if isinstance(sub_block, dict) and isinstance(sub_defaults, dict):
                for key, default_val in sub_defaults.items():
                    sub_block.setdefault(key, default_val)

    def _ensure_directory_exists(self, dir_path_str: Optional[str], dir_purpose: str, default_path: str) -> None:
        """Ensure a specified directory exists, creating it if necessary.

        Args:
            dir_path_str: The path string for the directory from configuration.
            dir_purpose: A string describing the purpose of the directory (for logging).
            default_path: The default path string to use if `dir_path_str` is None or empty.
        """
        path_to_use_str = dir_path_str if isinstance(dir_path_str, str) and dir_path_str.strip() else default_path
        if not path_to_use_str:  # pragma: no cover
            self._logger.error("Cannot ensure %s directory: No valid path for '%s'.", dir_purpose, dir_path_str)
            return
        try:
            path_to_use = Path(path_to_use_str)
            target_for_mkdir = (
                path_to_use.parent if path_to_use.suffix and dir_purpose.endswith("file") else path_to_use
            )
            if target_for_mkdir != Path():
                target_for_mkdir.mkdir(parents=True, exist_ok=True)
                self._logger.debug(
                    "Ensured %s directory structure exists for: %s", dir_purpose, target_for_mkdir.resolve()
                )
        except OSError as e:  # pragma: no cover
            self._logger.error(
                "Could not create/ensure %s directory for '%s': %s", dir_purpose, path_to_use_str, e, exc_info=True
            )

    def _resolve_value_from_env(self, env_var_name: Optional[str], value_purpose: str) -> Optional[str]:
        """Resolve a value from an environment variable if `env_var_name` is provided.

        Args:
            env_var_name: The name of the environment variable to check.
            value_purpose: A description of the value being resolved (for logging).

        Returns:
            The value from the environment variable if found and not empty, otherwise None.
        """
        if env_var_name and isinstance(env_var_name, str) and env_var_name.strip():
            env_val = os.environ.get(env_var_name.strip())
            if env_val:
                self._logger.info("Loaded %s from environment variable '%s'.", value_purpose, env_var_name)
                return env_val
            self._logger.debug("Environment variable '%s' for %s not set or is empty.", env_var_name, value_purpose)
        elif env_var_name:  # pragma: no cover
            self._logger.debug("Invalid environment variable name provided for %s: '%s'", value_purpose, env_var_name)
        return None

    def _deep_merge_configs(self, base_config: ConfigDict, override_config: ConfigDict) -> ConfigDict:
        """Deeply merge `override_config` into `base_config`. Modifies `base_config` in-place.

        Args:
            base_config: The base configuration dictionary to be modified.
            override_config: The configuration dictionary whose values will override
                             those in `base_config`.

        Returns:
            The modified `base_config` dictionary.
        """
        for key, value in override_config.items():
            if isinstance(value, dict) and key in base_config and isinstance(base_config[key], dict):
                self._deep_merge_configs(base_config[key], value)
            else:
                base_config[key] = value
        return base_config

    @staticmethod
    def _apply_cli_overrides_to_common(common_block: ConfigDict, cli_args_dict: ConfigDict) -> None:
        """Apply CLI overrides specifically to the 'common' configuration block.

        Args:
            common_block: The 'common' part of the configuration (modified in-place).
            cli_args_dict: Dictionary of CLI overrides relevant to common settings.
        """
        common_output_settings = common_block.setdefault("common_output_settings", {})
        logging_settings = common_block.setdefault("logging", {})

        if "name" in cli_args_dict:
            common_output_settings["default_output_name"] = cli_args_dict["name"]
        if "output" in cli_args_dict:
            common_output_settings["main_output_directory"] = cli_args_dict["output"]
        if "language" in cli_args_dict:
            common_output_settings["generated_text_language"] = cli_args_dict["language"]
        if "log_level" in cli_args_dict:
            logging_settings["log_level"] = cli_args_dict["log_level"]
        if "log_file" in cli_args_dict:
            logging_settings["log_file"] = cli_args_dict["log_file"]

    @staticmethod
    def _apply_cli_overrides_to_flow_specific(
        flow_specific_block: ConfigDict, cli_args_dict: ConfigDict, flow_name: str
    ) -> None:
        """Apply CLI overrides to the flow-specific configuration block.

        Args:
            flow_specific_block: The configuration block for the specific flow (modified in-place).
            cli_args_dict: Dictionary of CLI overrides relevant to this flow.
            flow_name: The name of the current flow (e.g., "FL01_code_analysis").
        """
        if "llm_provider" in cli_args_dict:
            flow_specific_block["active_llm_provider_id"] = cli_args_dict["llm_provider"]

        if flow_name == "FL01_code_analysis":
            source_opts = flow_specific_block.setdefault("source_options", {})
            if "include" in cli_args_dict:
                source_opts["include_patterns"] = cli_args_dict["include"]
            if "exclude" in cli_args_dict:
                source_opts["default_exclude_patterns"] = cli_args_dict["exclude"]
            if "max_size" in cli_args_dict:
                source_opts["max_file_size_bytes"] = cli_args_dict["max_size"]
        elif flow_name == "FL02_web_crawling":
            crawler_opts = flow_specific_block.setdefault("crawler_options", {})
            if "crawl_depth" in cli_args_dict:
                crawler_opts["max_depth_recursive"] = cli_args_dict["crawl_depth"]
            if "crawl_output_subdir" in cli_args_dict:
                crawler_opts["default_output_subdir_name"] = cli_args_dict["crawl_output_subdir"]

    def _apply_direct_llm_cli_overrides_to_profile(
        self, resolved_profile: LlmProfileDict, cli_llm_overrides: ConfigDict
    ) -> None:
        """Apply direct LLM overrides from CLI (model, api_key, base_url) to a resolved profile.

        Args:
            resolved_profile: The LLM profile dictionary (modified in-place).
            cli_llm_overrides: Dictionary of LLM-specific CLI overrides.
        """
        if "llm_model" in cli_llm_overrides:
            resolved_profile["model"] = cli_llm_overrides["llm_model"]
        if "api_key" in cli_llm_overrides:
            resolved_profile["api_key"] = cli_llm_overrides["api_key"]
        if "base_url" in cli_llm_overrides:
            resolved_profile["api_base_url"] = cli_llm_overrides["base_url"]

    def _resolve_active_llm_profile(
        self,
        active_llm_id_from_flow_config: Optional[str],
        cli_llm_overrides: ConfigDict,
        llm_profiles_from_global: list[LlmProfileDict],
        llm_default_options_from_common: LlmDefaultOptionsDict,
    ) -> LlmProfileDict:
        """Find, resolve (env vars), and merge an LLM profile including CLI overrides.

        Args:
            active_llm_id_from_flow_config: The active LLM ID from the flow's merged config.
            cli_llm_overrides: Dictionary of LLM-related CLI overrides (model, api_key, base_url).
            llm_profiles_from_global: List of all LLM profiles from the global config.
            llm_default_options_from_common: Default LLM options from common config.

        Returns:
            The fully resolved LLM profile dictionary.
        """
        resolved_profile = copy.deepcopy(llm_default_options_from_common)

        if not active_llm_id_from_flow_config:
            self._logger.warning("No 'active_llm_provider_id' for flow. Using common LLM defaults + CLI overrides.")
            self._apply_direct_llm_cli_overrides_to_profile(resolved_profile, cli_llm_overrides)
            return resolved_profile

        active_llm_profile_orig = next(
            (
                p
                for p in llm_profiles_from_global
                if isinstance(p, dict) and p.get("provider_id") == active_llm_id_from_flow_config
            ),
            None,
        )
        if not active_llm_profile_orig:  # pragma: no cover
            self._logger.error(f"Active LLM provider_id '{active_llm_id_from_flow_config}' not found. Using defaults.")
            self._apply_direct_llm_cli_overrides_to_profile(resolved_profile, cli_llm_overrides)
            return resolved_profile

        resolved_profile.update(copy.deepcopy(active_llm_profile_orig))

        if not resolved_profile.get("api_key") and "api_key" not in cli_llm_overrides:
            api_key_env_var = resolved_profile.get("api_key_env_var")
            api_key_from_env = self._resolve_value_from_env(
                api_key_env_var, f"API key for '{active_llm_id_from_flow_config}'"
            )
            if api_key_from_env:
                resolved_profile["api_key"] = api_key_from_env
            elif not resolved_profile.get("is_local_llm") and resolved_profile.get("provider") != "vertexai":
                self._logger.warning(f"API key for cloud LLM profile '{active_llm_id_from_flow_config}' not found.")

        self._apply_direct_llm_cli_overrides_to_profile(resolved_profile, cli_llm_overrides)

        if resolved_profile.get("provider") == "vertexai":  # pragma: no cover
            self._resolve_vertex_ai_specific_env_vars(resolved_profile, active_llm_id_from_flow_config)
        return resolved_profile

    def _resolve_vertex_ai_specific_env_vars(self, resolved_profile: LlmProfileDict, profile_id_for_log: str) -> None:
        """Resolve Vertex AI specific environment variables if not already set.

        Args:
            resolved_profile: The LLM profile dictionary for Vertex AI (modified in-place).
            profile_id_for_log: The ID of the profile for logging purposes.
        """
        for key, env_var_key, purpose in [
            ("vertex_project", "vertex_project_env_var", "Vertex project"),
            ("vertex_location", "vertex_location_env_var", "Vertex location"),
        ]:
            if not resolved_profile.get(key):
                env_var = resolved_profile.get(env_var_key)
                val_from_env = self._resolve_value_from_env(env_var, f"{purpose} for profile '{profile_id_for_log}'")
                if val_from_env:
                    resolved_profile[key] = val_from_env
                else:
                    self._logger.debug(f"Optional {purpose} for Vertex AI profile '{profile_id_for_log}' not set.")

    def _resolve_active_language_profile(
        self, active_lang_profile_id: Optional[str], language_profiles_from_global: list[LanguageProfileDict]
    ) -> Optional[LanguageProfileDict]:
        """Find and return the active language profile.

        Args:
            active_lang_profile_id: The ID of the language profile to find.
            language_profiles_from_global: List of all language profiles.

        Returns:
            The active language profile dictionary if found, else None.

        Raises:
            ConfigError: If `active_lang_profile_id` is provided but not found.
        """
        if not active_lang_profile_id:
            return None

        active_profile: Optional[LanguageProfileDict] = next(
            (
                lp
                for lp in language_profiles_from_global
                if isinstance(lp, dict) and lp.get("profile_id") == active_lang_profile_id
            ),
            None,
        )
        if not active_profile:
            raise ConfigError(
                f"Active language_profile_id '{active_lang_profile_id}' not found in profiles.language_profiles."
            )
        return active_profile

    def get_resolved_flow_config(
        self,
        flow_name: str,
        flow_default_config_path: Path,
        flow_schema: Optional[ConfigDict] = None,
        cli_args: Optional["argparse.Namespace"] = None,
    ) -> ConfigDict:
        """Load, merge, and resolve configuration for a specific flow.

        Args:
            flow_name: Identifier for the flow (e.g., "FL01_code_analysis").
            flow_default_config_path: Path to the flow's `config.default.json`.
            flow_schema: Optional JSON schema for the flow-specific config sections.
            cli_args: Optional parsed command-line arguments from `argparse.ArgumentParser`.

        Returns:
            A fully resolved configuration dictionary for the specified flow.
        """
        self._logger.info("Resolving configuration for flow: %s", flow_name)

        resolved_config = self._read_json_file(flow_default_config_path)
        if flow_schema:
            self._validate_against_schema(resolved_config, flow_schema, f"default config for flow '{flow_name}'")
        if flow_name not in resolved_config:  # pragma: no cover
            self._logger.warning(
                "Flow default config at '%s' does not have top-level key '%s'. Creating empty block.",
                flow_default_config_path,
                flow_name,
            )
            resolved_config.setdefault(flow_name, {})

        global_common_config = copy.deepcopy(self._global_config_data.get("common", {}))
        flow_common_block = resolved_config.setdefault("common", {})
        self._deep_merge_configs(flow_common_block, global_common_config)

        resolved_config["profiles"] = copy.deepcopy(self._global_config_data.get("profiles", {}))

        global_flow_specific_overrides = self._global_config_data.get(flow_name, {})
        if global_flow_specific_overrides:
            self._logger.debug("Merging global overrides for '%s' into resolved_config['%s']", flow_name, flow_name)
            self._deep_merge_configs(resolved_config[flow_name], global_flow_specific_overrides)

        cli_overrides_dict: ConfigDict = {}
        if cli_args:
            cli_overrides_dict = {
                k: v
                for k, v in vars(cli_args).items()
                if v is not None
                and k not in {"config", "flow", "repo", "dir", "crawl_url", "crawl_sitemap", "crawl_file"}
            }
            if "log_file" in cli_overrides_dict and str(cli_overrides_dict["log_file"]).upper() == "NONE":
                cli_overrides_dict["log_file"] = None

        self._apply_cli_overrides_to_common(resolved_config["common"], cli_overrides_dict)
        self._apply_cli_overrides_to_flow_specific(resolved_config[flow_name], cli_overrides_dict, flow_name)

        flow_settings_block = resolved_config.get(flow_name, {})
        active_llm_id = (
            flow_settings_block.get("active_llm_provider_id") if isinstance(flow_settings_block, dict) else None
        )
        llm_profiles = resolved_config.get("profiles", {}).get("llm_profiles", [])
        llm_default_opts = resolved_config.get("common", {}).get("llm_default_options", {})
        cli_llm_direct_overrides = {
            k: v for k, v in cli_overrides_dict.items() if k in {"llm_model", "api_key", "base_url"}
        }
        try:
            resolved_config["resolved_llm_config"] = self._resolve_active_llm_profile(
                active_llm_id, cli_llm_direct_overrides, llm_profiles, llm_default_opts
            )
        except ConfigError as e:  # pragma: no cover
            self._logger.error("Error resolving LLM profile for flow '%s': %s", flow_name, e)
            resolved_config["resolved_llm_config"] = copy.deepcopy(llm_default_opts)

        if flow_name == "FL01_code_analysis":
            self._resolve_code_analysis_specifics(resolved_config, flow_name)

        self._ensure_common_directories(resolved_config)

        self._logger.info("Successfully resolved configuration for flow: %s", flow_name)
        self._log_debug_resolved_config(resolved_config, flow_name)
        return resolved_config

    def _resolve_code_analysis_specifics(self, resolved_config: ConfigDict, flow_name: str) -> None:
        """Resolve GitHub token and language profile for code analysis flow.

        Args:
            resolved_config: The configuration dictionary (modified in-place).
            flow_name: The name of the flow (expected to be "FL01_code_analysis").
        """
        code_analysis_settings = resolved_config.get(flow_name, {})
        gh_token_env_var = code_analysis_settings.get("github_token_env_var", DEFAULT_GITHUB_TOKEN_ENV_VAR)
        direct_gh_token = code_analysis_settings.get("github_token")
        resolved_gh_token = (
            direct_gh_token
            if direct_gh_token and isinstance(direct_gh_token, str)
            else self._resolve_value_from_env(gh_token_env_var, "GitHub token")
        )
        code_analysis_settings["resolved_github_token"] = resolved_gh_token

        active_lang_id = code_analysis_settings.get("active_language_profile_id")
        lang_profiles_global = resolved_config.get("profiles", {}).get("language_profiles", [])
        resolved_lang_profile = self._resolve_active_language_profile(active_lang_id, lang_profiles_global)
        if resolved_lang_profile:
            source_config_block = code_analysis_settings.setdefault("source_config", {})
            source_config_block.update(resolved_lang_profile)
            self._logger.info("Resolved active language profile '%s' into source_config.", active_lang_id)
        elif active_lang_id:  # pragma: no cover
            self._logger.error(
                "Failed to resolve lang profile '%s'. 'source_config' may be incomplete.", active_lang_id
            )
        resolved_config[flow_name] = code_analysis_settings

    def _ensure_common_directories(self, resolved_config: ConfigDict) -> None:
        """Ensure common directories like log and cache directories exist.

        Args:
            resolved_config: The resolved configuration dictionary.
        """
        final_common_cfg_ensure = resolved_config.get("common", {})
        if isinstance(final_common_cfg_ensure, dict):
            logging_settings_ensure = final_common_cfg_ensure.get("logging", {})
            cache_settings_ensure = final_common_cfg_ensure.get("cache_settings", {})
            if isinstance(logging_settings_ensure, dict):
                self._ensure_directory_exists(
                    logging_settings_ensure.get("log_dir"), "logging directory", DEFAULT_LOG_DIR
                )
            if isinstance(cache_settings_ensure, dict):
                self._ensure_directory_exists(
                    cache_settings_ensure.get("llm_cache_file"), "LLM cache file", DEFAULT_LLM_CACHE_FILE
                )

    def _log_debug_resolved_config(self, resolved_config: ConfigDict, flow_name: str) -> None:  # pragma: no cover
        """Log the final resolved config for debugging, redacting sensitive info.

        Args:
            resolved_config: The final resolved configuration.
            flow_name: The name of the flow.
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            try:
                log_copy = json.loads(json.dumps(resolved_config))
                if isinstance(log_copy.get("resolved_llm_config"), dict):
                    if "api_key" in log_copy["resolved_llm_config"]:
                        log_copy["resolved_llm_config"]["api_key"] = "***REDACTED***"
                if isinstance(log_copy.get(flow_name), dict):
                    if "resolved_github_token" in log_copy[flow_name]:
                        log_copy[flow_name]["resolved_github_token"] = "***REDACTED***"
                self._logger.debug("Final resolved config for flow '%s': %s", flow_name, json.dumps(log_copy, indent=2))
            except (TypeError, ValueError) as e_dump:
                self._logger.debug("Could not serialize final config for logging: %s", e_dump)


def load_global_config(config_path_str: str = "config.json") -> ConfigDict:  # pragma: no cover
    """Load, validate, and process the main global application configuration.

    Args:
        config_path_str: Path to the global JSON configuration file.

    Returns:
        The processed global configuration dictionary.
    """
    module_logger.debug("load_global_config called with path: %s", config_path_str)
    loader = ConfigLoader(config_path_str)
    return loader._global_config_data


# End of src/sourcelens/config_loader.py
