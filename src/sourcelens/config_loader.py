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
import sys
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
    if hasattr(jsonschema_module, "exceptions"):
        jsonschema_exceptions_module = jsonschema_module.exceptions
    JSONSCHEMA_AVAILABLE = True
except ImportError:
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
WebSegmentationOptionsDict: TypeAlias = dict[str, Any]

AUTO_DETECT_OUTPUT_NAME: Final[str] = "auto-generated"
DEFAULT_MAIN_OUTPUT_DIR: Final[str] = "output"
DEFAULT_GENERATED_TEXT_LANGUAGE: Final[str] = "english"
DEFAULT_LOG_DIR: Final[str] = "logs"
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_LOG_FORMAT_MAIN: Final[str] = "%(asctime)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s"
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
DEFAULT_WEB_OUTPUT_SUBDIR_NAME: Final[str] = "crawled_web_content_standalone"
DEFAULT_WEB_PROCESSING_MODE: Final[str] = "minimalistic"
DEFAULT_WEB_MAX_DEPTH_RECURSIVE: Final[int] = 1
DEFAULT_WEB_USER_AGENT: Final[str] = "SourceLensBot/0.1 (https://github.com/openXFlow/sourceLensAI)"
DEFAULT_WEB_RESPECT_ROBOTS: Final[bool] = True
DEFAULT_WEB_MAX_CONCURRENT_REQUESTS: Final[int] = 3
DEFAULT_WEB_PAGE_TIMEOUT_MS: Final[int] = 30000
DEFAULT_WEB_WORD_COUNT_THRESHOLD_MARKDOWN: Final[int] = 50
DEFAULT_WEB_INCLUDE_CONTENT_INVENTORY: Final[bool] = True
DEFAULT_WEB_INCLUDE_CONTENT_REVIEW: Final[bool] = True
DEFAULT_LANGUAGE_PARSER_TYPE: Final[str] = "llm"
DEFAULT_WEB_SEGMENTATION_ENABLED: Final[bool] = True
DEFAULT_WEB_SEGMENTATION_MIN_CHUNK_CHAR_LENGTH: Final[int] = 150
DEFAULT_WEB_SEGMENTATION_HEADING_LEVELS: Final[list[int]] = [1, 2, 3]


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

WEB_ANALYSIS_SEGMENTATION_OPTIONS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "default": DEFAULT_WEB_SEGMENTATION_ENABLED},
        "min_chunk_char_length": {
            "type": "integer",
            "minimum": 0,
            "default": DEFAULT_WEB_SEGMENTATION_MIN_CHUNK_CHAR_LENGTH,
        },
        "heading_levels_to_split_on": {
            "type": "array",
            "items": {"type": "integer", "enum": [1, 2, 3, 4, 5, 6]},
            "default": DEFAULT_WEB_SEGMENTATION_HEADING_LEVELS,
        },
    },
    "additionalProperties": False,
    "default": {
        "enabled": DEFAULT_WEB_SEGMENTATION_ENABLED,
        "min_chunk_char_length": DEFAULT_WEB_SEGMENTATION_MIN_CHUNK_CHAR_LENGTH,
        "heading_levels_to_split_on": DEFAULT_WEB_SEGMENTATION_HEADING_LEVELS,
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
        "segmentation_options": WEB_ANALYSIS_SEGMENTATION_OPTIONS_SCHEMA,
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
        """Initialize ConfigLoader with the path to the global configuration file."""
        self._global_config_path = Path(global_config_path_str).resolve()
        self._logger = logging.getLogger(self.__class__.__name__)
        # Temporarily set logger level to DEBUG for ConfigLoader instance
        # to see its own debug messages during initialization.
        # This will be overridden by global logging setup in main.py later.
        self._logger.setLevel(logging.DEBUG)
        self._logger.addHandler(logging.StreamHandler(sys.stdout))  # Ensure it logs to console during init
        self._logger.propagate = False  # Prevent double logging if root logger also has handler

        self._logger.info("ConfigLoader __init__: Attempting to load global config from: %s", self._global_config_path)
        try:
            self._global_config_data = self._read_json_file(self._global_config_path)
            self._logger.info(
                "ConfigLoader __init__: Successfully read global config file: %s", self._global_config_path
            )
            self._logger.debug(
                "ConfigLoader __init__: Raw global config data loaded: %s",
                json.dumps(self._global_config_data, indent=2, default=str),
            )
            self._validate_against_schema(
                self._global_config_data, GLOBAL_ROOT_CONFIG_SCHEMA, f"global config '{self._global_config_path.name}'"
            )
            self._apply_defaults_to_common_section(self._global_config_data)
            self._logger.info("ConfigLoader __init__: Global configuration loaded and validated successfully.")
            self._logger.debug(
                "ConfigLoader __init__: Final _global_config_data after init processing: %s",
                json.dumps(self._global_config_data, indent=2, default=str),
            )
        except FileNotFoundError:
            self._logger.warning(
                "ConfigLoader __init__: Global config file '%s' not found. Using empty global config. "
                "Flows will rely on their defaults and CLI overrides.",
                self._global_config_path,
            )
            self._global_config_data = {}
        except ConfigError as e:
            self._logger.error(
                "ConfigLoader __init__: Failed to load or validate global config '%s': %s. Using empty global config.",
                self._global_config_path,
                e,
                exc_info=True,
            )
            self._global_config_data = {}
        finally:
            # Reset a bit so it doesn't interfere too much with main logging if it's set up differently
            self._logger.propagate = True

    def _ensure_jsonschema_available(self) -> None:  # pragma: no cover
        if not JSONSCHEMA_AVAILABLE:
            raise ImportError("The 'jsonschema' library is required for schema validation. Please install it.")

    def _read_json_file(self, file_path: Path) -> ConfigDict:
        """Read and parse a JSON configuration file."""
        if not file_path.is_file():
            self._logger.error("Configuration file not found at resolved path: '%s'", file_path)
            raise FileNotFoundError(f"Configuration file not found: '{file_path}'")
        try:
            with file_path.open(encoding="utf-8") as f:
                loaded_data: Any = json.load(f)
                if not isinstance(loaded_data, dict):
                    msg = f"Configuration in '{file_path}' is not a valid JSON object (dictionary)."
                    raise ConfigError(msg)
                self._logger.debug("Successfully parsed JSON from '%s'", file_path)
                return cast(ConfigDict, loaded_data)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON syntax in '{file_path}': {e!s}") from e
        except OSError as e:
            raise ConfigError(f"Could not read configuration file '{file_path}': {e!s}") from e

    def _validate_against_schema(self, instance: ConfigDict, schema: ConfigDict, file_description: str) -> None:
        """Validate a configuration instance against a given JSON schema."""
        self._ensure_jsonschema_available()
        if not (
            jsonschema_validate_func is not None
            and jsonschema_exceptions_module is not None
            and JsonSchemaValidationError_type is not None
            and hasattr(jsonschema_exceptions_module, "ValidationError")
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
            log_msg_l2 = f"{e!s}"
            self._logger.error(log_msg_l1 + log_msg_l2, exc_info=True)
            raise ConfigError(log_msg_l1 + log_msg_l2) from e

    def _load_and_validate_global_config(self) -> None:
        pass

    def _apply_defaults_to_common_section(self, config_dict: ConfigDict) -> None:
        """Apply default values to the 'common' section if keys are missing."""
        common_cfg: ConfigDict = config_dict.setdefault("common", {})
        common_schema_props = COMMON_SCHEMA.get("properties", {})

        for sub_key, sub_schema in common_schema_props.items():
            sub_block = common_cfg.setdefault(sub_key, {})
            sub_defaults = sub_schema.get("default", {})
            if isinstance(sub_block, dict) and isinstance(sub_defaults, dict):
                for key, default_val in sub_defaults.items():
                    sub_block.setdefault(key, default_val)

    def _ensure_directory_exists(self, dir_path_str: Optional[str], dir_purpose: str, default_path: str) -> None:
        """Ensure a specified directory exists, creating it if necessary."""
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
        """Resolve a value from an environment variable if `env_var_name` is provided."""
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
        """Deeply merge `override_config` into `base_config`. Modifies `base_config` in-place."""
        for key, value in override_config.items():
            if isinstance(value, dict) and key in base_config and isinstance(base_config[key], dict):
                self._deep_merge_configs(base_config[key], value)
            else:
                base_config[key] = value
        return base_config

    @staticmethod
    def _apply_cli_overrides_to_common(common_block: ConfigDict, cli_args_dict: ConfigDict) -> None:
        """Apply CLI overrides specifically to the 'common' configuration block."""
        common_output_settings = common_block.setdefault("common_output_settings", {})
        logging_settings = common_block.setdefault("logging", {})

        if "name" in cli_args_dict:
            common_output_settings["default_output_name"] = cli_args_dict["name"]
        if "output" in cli_args_dict:
            common_output_settings["main_output_directory"] = str(cli_args_dict["output"])
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
        """Apply CLI overrides to the flow-specific configuration block."""
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
        """Apply direct LLM overrides from CLI (model, api_key, base_url) to a resolved profile."""
        if "llm_model" in cli_llm_overrides:
            resolved_profile["model"] = cli_llm_overrides["llm_model"]
            self._logger.debug("CLI override: LLM model set to '%s'", cli_llm_overrides["llm_model"])
        if "api_key" in cli_llm_overrides:
            resolved_profile["api_key"] = cli_llm_overrides["api_key"]
            self._logger.debug("CLI override: LLM API key was provided (value redacted).")
        if "base_url" in cli_llm_overrides:
            resolved_profile["api_base_url"] = cli_llm_overrides["base_url"]
            self._logger.debug("CLI override: LLM base_url set to '%s'", cli_llm_overrides["base_url"])

    def _get_initial_llm_profile(
        self,
        active_llm_id: Optional[str],
        llm_profiles_from_global: list[LlmProfileDict],
        llm_default_options: LlmDefaultOptionsDict,
    ) -> LlmProfileDict:
        """Get the initial LLM profile by merging defaults with the specified active profile."""
        merged_profile = copy.deepcopy(llm_default_options)
        self._logger.debug("LLM Profile Resolution Step 1: Initial defaults from common: %s", merged_profile)

        if not active_llm_id:
            self._logger.warning("No 'active_llm_provider_id' specified. Using only common LLM defaults for base.")
            return merged_profile

        self._logger.debug("LLM Profile Resolution Step 1: Finding profile_id: '%s' in global profiles.", active_llm_id)
        active_profile_base = next(
            (p for p in llm_profiles_from_global if isinstance(p, dict) and p.get("provider_id") == active_llm_id),
            None,
        )

        if not active_profile_base:
            self._logger.error(
                f"LLM Profile Resolution Step 1: Active LLM provider_id '{active_llm_id}' not found in global profiles. "  # noqa: E501
                "Using only common LLM defaults for base."
            )
            return merged_profile

        base_profile_log = {
            k: (v if k != "api_key" else (f"{str(v)[:3]}***" if v else None)) for k, v in active_profile_base.items()
        }
        self._logger.debug("LLM Profile Resolution Step 1: Found base profile in global: %s", base_profile_log)

        merged_profile.update(copy.deepcopy(active_profile_base))
        merged_profile_log = {
            k: (v if k != "api_key" else (f"{str(v)[:3]}***" if v else None)) for k, v in merged_profile.items()
        }
        self._logger.debug("LLM Profile Resolution Step 1: After merging base profile: %s", merged_profile_log)
        return merged_profile

    def _finalize_llm_profile_with_env_and_cli(
        self, profile_to_finalize: LlmProfileDict, active_llm_id: Optional[str], cli_llm_overrides: ConfigDict
    ) -> None:
        """Finalize LLM profile by resolving ENV vars and applying CLI overrides. Modifies in-place."""
        profile_id_for_log = active_llm_id or "N/A_PROFILE_ID"
        log_profile_before = {
            k: (v if k != "api_key" else (f"{str(v)[:3]}***" if v else None)) for k, v in profile_to_finalize.items()
        }
        self._logger.debug(
            "LLM Profile Finalization for '%s': State before ENV/CLI: %s", profile_id_for_log, log_profile_before
        )

        if not profile_to_finalize.get("api_key") and "api_key" not in cli_llm_overrides:
            api_key_env_var = profile_to_finalize.get("api_key_env_var")
            self._logger.debug(
                "LLM Profile Finalization: API key not in profile. Trying ENV var: '%s'", api_key_env_var
            )
            api_key_from_env = self._resolve_value_from_env(api_key_env_var, f"API key for '{profile_id_for_log}'")
            if api_key_from_env:
                profile_to_finalize["api_key"] = api_key_from_env
                self._logger.debug("LLM Profile Finalization: API key loaded from ENV for '%s'.", profile_id_for_log)
            elif not profile_to_finalize.get("is_local_llm") and profile_to_finalize.get("provider") != "vertexai":
                self._logger.warning(
                    "LLM Profile Finalization: API key for cloud LLM profile '%s' not found in config or ENV var '%s'.",
                    profile_id_for_log,
                    api_key_env_var,
                )
        elif profile_to_finalize.get("api_key"):
            self._logger.debug(
                "LLM Profile Finalization: API key was already present in profile for '%s' (before CLI).",
                profile_id_for_log,
            )
        elif "api_key" in cli_llm_overrides:
            self._logger.debug(
                "LLM Profile Finalization: API key will be set by CLI override for '%s'.", profile_id_for_log
            )

        self._apply_direct_llm_cli_overrides_to_profile(profile_to_finalize, cli_llm_overrides)
        log_profile_after_cli = {
            k: (v if k != "api_key" else (f"{str(v)[:3]}***" if v else None)) for k, v in profile_to_finalize.items()
        }
        self._logger.debug(
            "LLM Profile Finalization for '%s': After applying direct CLI overrides: %s",
            profile_id_for_log,
            log_profile_after_cli,
        )

        if profile_to_finalize.get("provider") == "vertexai":  # pragma: no cover
            self._resolve_vertex_ai_specific_env_vars(profile_to_finalize, profile_id_for_log)

        api_key_present = bool(profile_to_finalize.get("api_key"))
        is_cloud_provider_needing_key = not profile_to_finalize.get("is_local_llm") and profile_to_finalize.get(
            "provider"
        ) not in ["vertexai", "openai_compatible"]

        if not api_key_present and is_cloud_provider_needing_key:
            final_check_msg_part1 = "FINAL CHECK: API key for cloud LLM profile "
            final_check_msg_part2 = f"'{profile_id_for_log}' (provider: {profile_to_finalize.get('provider')}) "
            final_check_msg_part3 = "is STILL MISSING after all checks."
            self._logger.error(final_check_msg_part1 + final_check_msg_part2 + final_check_msg_part3)
            print(
                f"Warning: API key for cloud LLM profile '{profile_id_for_log}' not found in config or "
                f"ENV var '{profile_to_finalize.get('api_key_env_var')}'.",
                file=sys.stderr,
            )
        elif api_key_present:
            self._logger.info("API key successfully resolved for LLM profile '%s'.", profile_id_for_log)
        else:
            self._logger.info(
                "LLM profile '%s' (provider: %s) does not require a direct api_key in profile or is local.",
                profile_id_for_log,
                profile_to_finalize.get("provider"),
            )

    def _resolve_active_llm_profile(
        self,
        active_llm_id_from_flow_config: Optional[str],
        cli_llm_overrides: ConfigDict,
        llm_profiles_from_global: list[LlmProfileDict],
        llm_default_options_from_common: LlmDefaultOptionsDict,
    ) -> LlmProfileDict:
        """Find, resolve (env vars), and merge an LLM profile including CLI overrides. (Orchestrator)."""
        self._logger.debug(
            "Orchestrating LLM profile resolution for ID: '%s'", active_llm_id_from_flow_config or "None specified"
        )
        resolved_profile = self._get_initial_llm_profile(
            active_llm_id_from_flow_config, llm_profiles_from_global, llm_default_options_from_common
        )
        self._finalize_llm_profile_with_env_and_cli(resolved_profile, active_llm_id_from_flow_config, cli_llm_overrides)
        final_log_profile = {
            k: (v if k != "api_key" else (f"{str(v)[:3]}***" if v else None)) for k, v in resolved_profile.items()
        }
        self._logger.debug(
            "LLM profile resolution complete for ID '%s'. Final profile: %s",
            active_llm_id_from_flow_config or "None specified",
            final_log_profile,
        )
        return resolved_profile

    def _resolve_vertex_ai_specific_env_vars(self, resolved_profile: LlmProfileDict, profile_id_for_log: str) -> None:
        """Resolve Vertex AI specific environment variables if not already set."""
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
        """Find and return the active language profile."""
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
        """Load, merge, and resolve configuration for a specific flow."""
        self._logger.info("Resolving configuration for flow: %s", flow_name)
        self._logger.debug("Global config path being used by ConfigLoader: %s", self._global_config_path)
        self._logger.debug("Flow default config path to be loaded: %s", flow_default_config_path)

        default_flow_cfg = self._read_json_file(flow_default_config_path)
        self._logger.debug(
            "Loaded default flow config for '%s': %s", flow_name, json.dumps(default_flow_cfg, indent=2, default=str)
        )
        if flow_schema:  # pragma: no cover
            self._validate_against_schema(default_flow_cfg, flow_schema, f"default config for flow '{flow_name}'")

        if flow_name not in default_flow_cfg:  # pragma: no cover
            self._logger.warning(
                "Flow default config at '%s' does not have top-level key '%s'. Creating empty block.",
                flow_default_config_path,
                flow_name,
            )
            default_flow_cfg.setdefault(flow_name, {})

        resolved_config = self._prepare_initial_resolved_config(default_flow_cfg)
        cli_overrides_dict = self._collect_cli_overrides(cli_args)
        self._apply_cli_overrides(resolved_config, cli_overrides_dict, flow_name)

        self._resolve_llm_and_flow_specifics(resolved_config, cli_overrides_dict, flow_name)

        self._ensure_common_directories(resolved_config)

        self._logger.info("Successfully resolved configuration for flow: %s", flow_name)
        self._log_debug_resolved_config(resolved_config, flow_name)
        return resolved_config

    def _prepare_initial_resolved_config(self, default_flow_cfg: ConfigDict) -> ConfigDict:
        resolved_config = copy.deepcopy(self._global_config_data)
        resolved_config.setdefault("profiles", {"llm_profiles": [], "language_profiles": []})
        resolved_config.setdefault("common", {})
        self._apply_defaults_to_common_section(resolved_config)
        self._logger.debug(
            "Initial resolved_config (from global or empty + common defaults): %s",
            json.dumps(resolved_config, indent=2, default=str),
        )
        self._deep_merge_configs(resolved_config, default_flow_cfg)
        self._logger.debug(
            "Resolved_config after deep_merging flow defaults into it: %s",
            json.dumps(resolved_config, indent=2, default=str),
        )
        return resolved_config

    def _collect_cli_overrides(self, cli_args: Optional["argparse.Namespace"]) -> ConfigDict:
        cli_overrides_dict: ConfigDict = {}
        if cli_args:
            cli_overrides_dict = {
                k: v
                for k, v in vars(cli_args).items()
                if v is not None
                and k
                not in {
                    "config",
                    "flow_command",
                    "internal_flow_name",
                    "repo",
                    "dir",
                    "crawl_url",
                    "crawl_sitemap",
                    "crawl_file",
                }
            }
            if "log_file" in cli_overrides_dict and str(cli_overrides_dict["log_file"]).upper() == "NONE":
                cli_overrides_dict["log_file"] = None
            self._logger.debug("CLI overrides collected to apply: %s", cli_overrides_dict)
        return cli_overrides_dict

    def _apply_cli_overrides(self, resolved_config: ConfigDict, cli_overrides_dict: ConfigDict, flow_name: str) -> None:
        common_block_for_cli = resolved_config.setdefault("common", {})
        self._apply_defaults_to_common_section(resolved_config)
        self._apply_cli_overrides_to_common(common_block_for_cli, cli_overrides_dict)

        flow_specific_block_for_cli = resolved_config.setdefault(flow_name, {})
        self._apply_cli_overrides_to_flow_specific(flow_specific_block_for_cli, cli_overrides_dict, flow_name)
        self._logger.debug(
            "Resolved_config after applying all CLI overrides: %s", json.dumps(resolved_config, indent=2, default=str)
        )

    def _resolve_llm_and_flow_specifics(
        self,
        resolved_config: ConfigDict,
        cli_overrides_dict: ConfigDict,
        flow_name: str,
    ) -> None:
        flow_specific_block_for_cli = resolved_config.setdefault(flow_name, {})
        self._logger.debug(
            "Flow specific block for '%s' BEFORE LLM profile resolution: %s",
            flow_name,
            json.dumps(flow_specific_block_for_cli, indent=2, default=str),
        )

        active_llm_id = flow_specific_block_for_cli.get("active_llm_provider_id")
        self._logger.debug("Active LLM provider ID from merged flow config for '%s': %s", flow_name, active_llm_id)

        llm_profiles_from_resolved_config = resolved_config.get("profiles", {}).get("llm_profiles", [])
        self._logger.debug(
            "LLM profiles available in resolved_config for LLM profile resolution: %s",
            json.dumps(llm_profiles_from_resolved_config, indent=2, default=lambda o: f"<<{type(o)}>>"),
        )

        llm_default_opts_from_resolved_common = resolved_config.get("common", {}).get("llm_default_options", {})
        cli_llm_direct_overrides = {
            k: v for k, v in cli_overrides_dict.items() if k in {"llm_model", "api_key", "base_url"}
        }
        try:
            resolved_config["resolved_llm_config"] = self._resolve_active_llm_profile(
                active_llm_id,
                cli_llm_direct_overrides,
                llm_profiles_from_resolved_config,
                llm_default_opts_from_resolved_common,
            )
            log_llm_config_safe = {
                k: (v if k != "api_key" else (f"{str(v)[:3]}***" if v else None))
                for k, v in resolved_config["resolved_llm_config"].items()
            }
            self._logger.debug(
                "Final resolved_llm_config in get_resolved_flow_config: %s", json.dumps(log_llm_config_safe, indent=2)
            )

        except ConfigError as e:  # pragma: no cover
            self._logger.error("Error resolving LLM profile for flow '%s': %s", flow_name, e)
            resolved_config["resolved_llm_config"] = copy.deepcopy(llm_default_opts_from_resolved_common)

        if flow_name == "FL01_code_analysis":
            self._resolve_code_analysis_specifics(resolved_config, flow_name)
        elif flow_name == "FL02_web_crawling":
            seg_opts_schema_defaults = WEB_ANALYSIS_SEGMENTATION_OPTIONS_SCHEMA.get("default", {})
            current_seg_opts = flow_specific_block_for_cli.setdefault("segmentation_options", {})
            for k_seg, v_seg_default in seg_opts_schema_defaults.items():
                current_seg_opts.setdefault(k_seg, v_seg_default)
            self._logger.debug("Applied defaults to segmentation_options for %s: %s", flow_name, current_seg_opts)

    def _resolve_code_analysis_specifics(self, resolved_config: ConfigDict, flow_name: str) -> None:
        """Resolve GitHub token and language profile for code analysis flow."""
        code_analysis_settings = resolved_config.setdefault(flow_name, {})
        gh_token_env_var = code_analysis_settings.get("github_token_env_var", DEFAULT_GITHUB_TOKEN_ENV_VAR)
        direct_gh_token = code_analysis_settings.get("github_token")
        resolved_gh_token = (
            direct_gh_token
            if direct_gh_token and isinstance(direct_gh_token, str)
            else self._resolve_value_from_env(gh_token_env_var, "GitHub token")
        )
        code_analysis_settings["resolved_github_token"] = resolved_gh_token
        self._logger.debug(
            "Resolved GitHub token for %s: %s", flow_name, "***REDACTED***" if resolved_gh_token else "None"
        )

        active_lang_id = code_analysis_settings.get("active_language_profile_id")
        lang_profiles_global = resolved_config.get("profiles", {}).get("language_profiles", [])
        resolved_lang_profile = self._resolve_active_language_profile(active_lang_id, lang_profiles_global)

        source_config_block = code_analysis_settings.setdefault("source_config", {})
        if resolved_lang_profile:
            source_config_block.update(resolved_lang_profile)
            self._logger.info("Resolved active language profile '%s' into source_config.", active_lang_id)
        elif active_lang_id:  # pragma: no cover
            self._logger.error(
                "Failed to resolve lang profile '%s'. 'source_config' may be incomplete or use defaults.",
                active_lang_id,
            )
        source_options_schema_defaults = CODE_ANALYSIS_SOURCE_OPTIONS_SCHEMA.get("default", {})
        current_source_options = code_analysis_settings.setdefault("source_options", {})
        for k_so, v_so_default in source_options_schema_defaults.items():
            current_source_options.setdefault(k_so, v_so_default)
        self._logger.debug("Applied defaults to source_options for %s: %s", flow_name, current_source_options)

    def _ensure_common_directories(self, resolved_config: ConfigDict) -> None:
        """Ensure common directories like log and cache directories exist."""
        final_common_cfg_ensure = resolved_config.get("common", {})
        if isinstance(final_common_cfg_ensure, dict):
            logging_settings_ensure = final_common_cfg_ensure.get("logging", {})
            cache_settings_ensure = final_common_cfg_ensure.get("cache_settings", {})
            common_output_settings_ensure = final_common_cfg_ensure.get("common_output_settings", {})

            if isinstance(logging_settings_ensure, dict):
                self._ensure_directory_exists(
                    logging_settings_ensure.get("log_dir"), "logging directory", DEFAULT_LOG_DIR
                )
            if isinstance(cache_settings_ensure, dict):
                self._ensure_directory_exists(
                    cache_settings_ensure.get("llm_cache_file"), "LLM cache file", DEFAULT_LLM_CACHE_FILE
                )
            if isinstance(common_output_settings_ensure, dict):
                self._ensure_directory_exists(
                    common_output_settings_ensure.get("main_output_directory"),
                    "main output directory",
                    DEFAULT_MAIN_OUTPUT_DIR,
                )

    def _log_debug_resolved_config(self, resolved_config: ConfigDict, flow_name: str) -> None:  # pragma: no cover
        """Log the final resolved config for debugging, redacting sensitive info."""
        if self._logger.isEnabledFor(logging.DEBUG):
            try:
                log_copy = json.loads(json.dumps(resolved_config, default=str))
                if isinstance(log_copy.get("resolved_llm_config"), dict):
                    if "api_key" in log_copy["resolved_llm_config"]:
                        log_copy["resolved_llm_config"]["api_key"] = "***REDACTED***"
                if flow_name in log_copy and isinstance(log_copy.get(flow_name), dict):
                    if "resolved_github_token" in log_copy[flow_name]:
                        log_copy[flow_name]["resolved_github_token"] = "***REDACTED***"
                    if flow_name == "FL02_web_crawling" and "segmentation_options" in log_copy[flow_name]:
                        self._logger.debug(
                            "Resolved segmentation_options for %s: %s",
                            flow_name,
                            json.dumps(log_copy[flow_name]["segmentation_options"], indent=2),
                        )

                self._logger.debug("Final resolved_config for flow '%s': %s", flow_name, json.dumps(log_copy, indent=2))
            except (TypeError, ValueError) as e_dump:
                self._logger.debug("Could not serialize final config for logging: %s", e_dump)


def load_global_config(config_path_str: str = "config.json") -> ConfigDict:  # pragma: no cover
    """Load, validate, and process the main global application configuration."""
    # module_logger tu nie je definovaný, použijeme ConfigLoader._logger, ale to je až po __init__
    # Preto priamo použijeme logging.getLogger pre tento účel.
    temp_logger = logging.getLogger("sourcelens.config_loader.load_global_config")
    temp_logger.debug("load_global_config called with path: %s", config_path_str)
    loader = ConfigLoader(config_path_str)
    return loader._global_config_data


# End of src/sourcelens/config_loader.py
