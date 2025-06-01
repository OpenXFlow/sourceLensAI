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

This module handles reading settings from a JSON file, validating against a schema,
resolving secrets from environment variables, and processing active profiles
for code and web analysis modes. It provides a structured configuration object
for the application.
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
LlmProfileDict: TypeAlias = dict[str, Any]
LanguageProfileDict: TypeAlias = dict[str, Any]
CommonOutputSettingsDict: TypeAlias = dict[str, Any]
LoggingConfigDict: TypeAlias = dict[str, Any]
CacheSettingsDict: TypeAlias = dict[str, Any]
LlmDefaultOptionsDict: TypeAlias = dict[str, Any]
SourceOptionsDict: TypeAlias = dict[str, Any]
CodeDiagramGenerationDict: TypeAlias = dict[str, Any]
CodeOutputOptionsDict: TypeAlias = dict[str, Any]
WebCrawlerOptionsDict: TypeAlias = dict[str, Any]
WebOutputOptionsDict: TypeAlias = dict[str, Any]
ResolvedCodeAnalysisConfig: TypeAlias = dict[str, Any]
ResolvedWebAnalysisConfig: TypeAlias = dict[str, Any]


# --- Constants ---
DEFAULT_OUTPUT_NAME_FALLBACK: Final[str] = "sourcelens_output"
AUTO_DETECT_OUTPUT_NAME: Final[str] = "auto-generated"
DEFAULT_MAIN_OUTPUT_DIR: Final[str] = "output"
DEFAULT_GENERATED_TEXT_LANGUAGE: Final[str] = "english"
DEFAULT_LOG_DIR: Final[str] = "logs"
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_USE_LLM_CACHE: Final[bool] = True
DEFAULT_LLM_CACHE_FILE: Final[str] = ".cache/llm_cache.json"
DEFAULT_LLM_MAX_RETRIES: Final[int] = 3
DEFAULT_LLM_RETRY_WAIT_SECONDS: Final[int] = 10

DEFAULT_CODE_ANALYSIS_ENABLED: Final[bool] = True
DEFAULT_GITHUB_TOKEN_ENV_VAR: Final[str] = "GITHUB_TOKEN"
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
DEFAULT_WEB_USER_AGENT: Final[str] = "SourceLensBot/0.1 (https://github.com/darijo2yahoocom/sourceLensAI)"
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


# --- JSON Schema Definitions ---

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
    },
    "additionalProperties": False,
    "default": {"log_dir": DEFAULT_LOG_DIR, "log_level": DEFAULT_LOG_LEVEL},
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
    "additionalProperties": False,
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

CODE_ANALYSIS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "default": DEFAULT_CODE_ANALYSIS_ENABLED},
        "github_token_env_var": {"type": ["string", "null"], "default": DEFAULT_GITHUB_TOKEN_ENV_VAR},
        "github_token": {"type": ["string", "null"], "default": None},
        "active_language_profile_id": {"type": "string"},
        "source_options": CODE_ANALYSIS_SOURCE_OPTIONS_SCHEMA,
        "diagram_generation": CODE_ANALYSIS_DIAGRAM_GENERATION_SCHEMA,
        "output_options": CODE_ANALYSIS_OUTPUT_OPTIONS_SCHEMA,
        "active_llm_provider_id": {"type": "string"},
    },
    "required": ["active_language_profile_id", "active_llm_provider_id"],
    "additionalProperties": False,
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

WEB_ANALYSIS_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "default": DEFAULT_WEB_ANALYSIS_ENABLED},
        "active_llm_provider_id": {"type": "string"},
        "crawler_options": WEB_ANALYSIS_CRAWLER_OPTIONS_SCHEMA,
        "output_options": WEB_ANALYSIS_OUTPUT_OPTIONS_SCHEMA,
    },
    "required": ["active_llm_provider_id"],
    "additionalProperties": False,
}

LANGUAGE_PROFILE_SCHEMA_ITEM: ConfigDict = {
    "type": "object",
    "properties": {
        "profile_id": {"type": "string"},
        "language_name_for_llm": {"type": "string"},
        "parser_type": {"type": "string", "enum": ["ast", "llm", "none"], "default": DEFAULT_LANGUAGE_PARSER_TYPE},
        "include_patterns": {"type": "array", "items": {"type": "string"}, "default": []},
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
        "api_key_env_var": {"type": ["string", "null"], "default": None},
        "api_key": {"type": ["string", "null"], "default": None},
        "api_base_url": {"type": ["string", "null"], "default": None},
        "vertex_project_env_var": {"type": ["string", "null"], "default": None},
        "vertex_location_env_var": {"type": ["string", "null"], "default": None},
        "vertex_project": {"type": ["string", "null"], "default": None},
        "vertex_location": {"type": ["string", "null"], "default": None},
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

ROOT_CONFIG_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        "common": COMMON_SCHEMA,
        "code_analysis": CODE_ANALYSIS_SCHEMA,
        "web_analysis": WEB_ANALYSIS_SCHEMA,
        "profiles": PROFILES_SCHEMA,
    },
    "required": ["common", "code_analysis", "web_analysis", "profiles"],
    "additionalProperties": False,
}


class ConfigError(Exception):
    """Custom exception for configuration loading or validation errors."""


logger: logging.Logger = logging.getLogger(__name__)


class ConfigLoader:
    """Handles loading, validation, and processing of application configuration.

    This class is responsible for reading a JSON configuration file,
    validating its structure against a predefined schema, applying default
    values, resolving environment variables for sensitive data (like API keys),
    and selecting active profiles for different analysis modes (code, web).
    The final output is a processed configuration dictionary that the rest of
    the application can use.
    """

    _config_data: ConfigDict
    _config_path: Path

    def __init__(self, config_path_str: str) -> None:
        """Initialize the ConfigLoader.

        Args:
            config_path_str (str): The path to the JSON configuration file.
        """
        self._config_path = Path(config_path_str).resolve()
        self._config_data = {}

    def _ensure_jsonschema_available(self) -> None:
        """Raise ImportError if jsonschema is not installed or its components are missing.

        Raises:
            ImportError: If the 'jsonschema' library is not available.
        """
        if not JSONSCHEMA_AVAILABLE:
            raise ImportError("The 'jsonschema' library is required for config validation. Please install it.")

    def _read_config_file(self) -> None:
        """Read and parse the JSON configuration file into `self._config_data`.

        Raises:
            FileNotFoundError: If the configuration file specified by `self._config_path`
                               is not found.
            ConfigError: If the file cannot be read due to an OS error (e.g., permissions)
                         or if it contains invalid JSON syntax.
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
        """Validate the loaded configuration data against the `ROOT_CONFIG_SCHEMA`.

        Uses the `jsonschema` library for validation if available.

        Raises:
            ConfigError: If schema validation fails, providing details about the
                         location and nature of the validation error.
            RuntimeError: If `jsonschema` components (validator function or
                          `ValidationError` exception) are unexpectedly unavailable
                          despite an initial successful import check. This indicates
                          an issue with the `jsonschema` installation or environment.
            ImportError: If the `jsonschema` library itself is not installed.
        """
        self._ensure_jsonschema_available()
        if (
            jsonschema_validate_func is None
            or jsonschema is None
            or not hasattr(jsonschema, "exceptions")
            or not hasattr(jsonschema.exceptions, "ValidationError")  # type: ignore[union-attr]
        ):
            # This should ideally not be reached if _ensure_jsonschema_available passes.
            raise RuntimeError("jsonschema components not available for validation despite initial check.")

        try:
            # jsonschema.exceptions.ValidationError is the correct type here.
            validation_error_type: type[ValidationError] = jsonschema.exceptions.ValidationError  # type: ignore[union-attr]
            jsonschema_validate_func(instance=self._config_data, schema=ROOT_CONFIG_SCHEMA)
            logger.debug("Configuration schema validation passed for %s.", self._config_path.name)
        except validation_error_type as e_val_err:  # type: ignore[misc] # For jsonschema.exceptions.ValidationError
            path_str = " -> ".join(map(str, e_val_err.path)) if e_val_err.path else "root"
            err_msg = f"Config error in '{self._config_path.name}' at '{path_str}': {e_val_err.message}"
            logger.debug(
                "Schema validation failed. Instance: %s. Path: %s. Validator: %s. Schema path: %s",
                e_val_err.instance,
                path_str,
                e_val_err.validator,
                " -> ".join(map(str, e_val_err.schema_path)),
            )
            raise ConfigError(err_msg) from e_val_err
        except Exception as e:  # Catch any other unexpected error during validation
            raise ConfigError(f"Unexpected error during schema validation: {e!s}") from e

    def _ensure_directory_exists(self, dir_path_str: Optional[str], dir_purpose: str, default_path: str) -> None:
        """Ensure a specified directory exists, creating it if necessary.

        Logs the outcome of the operation. If `dir_path_str` is None or empty,
        the `default_path` is used.

        Args:
            dir_path_str: The path string for the directory from the configuration.
            dir_purpose: A human-readable description of the directory's purpose (for logging).
            default_path: The default path string to use if `dir_path_str` is invalid.
        """
        path_to_use_str = dir_path_str if isinstance(dir_path_str, str) and dir_path_str.strip() else default_path
        if not path_to_use_str:  # Should not happen if default_path is always valid
            logger.error("Cannot ensure %s directory: No valid path for '%s'.", dir_purpose, dir_path_str)
            return
        try:
            path_to_use = Path(path_to_use_str)
            # For cache file, ensure its parent directory exists. For log dir, ensure the dir itself.
            target_for_mkdir = (
                path_to_use.parent if dir_purpose == "LLM cache file" and path_to_use.suffix else path_to_use
            )

            if target_for_mkdir != Path():  # Avoid trying to mkdir on '.' or if path_to_use is empty
                target_for_mkdir.mkdir(parents=True, exist_ok=True)
                logger.debug("Ensured %s directory structure exists for: %s", dir_purpose, target_for_mkdir.resolve())
        except OSError as e:
            logger.error(
                "Could not create/ensure %s directory for '%s': %s", dir_purpose, path_to_use_str, e, exc_info=True
            )
        except Exception as e_unexp:  # Catch any other unexpected error
            logger.error(
                "Unexpected error ensuring %s dir for '%s': %s", dir_purpose, path_to_use_str, e_unexp, exc_info=True
            )

    def _apply_defaults_and_populate_common(self) -> None:
        """Apply default values from the schema to the 'common' section and its subsections.

        This method ensures that the 'common' section and its nested dictionaries
        (like 'common_output_settings', 'logging', 'cache_settings', 'llm_default_options')
        exist in `self._config_data`. If they or any of their fields are missing,
        their default values as defined in their respective schemas are applied.
        It also calls `_ensure_directory_exists` for log and cache paths.
        """
        cfg = self._config_data
        common_cfg: ConfigDict = cfg.setdefault("common", {})  # Ensures 'common' key exists
        common_schema_props = COMMON_SCHEMA.get("properties", {})  # Schema for 'common'

        # Process 'common_output_settings'
        common_output_cfg: CommonOutputSettingsDict = common_cfg.setdefault("common_output_settings", {})
        output_defaults = common_schema_props.get("common_output_settings", {}).get("default", {})
        for key, default_val in output_defaults.items():
            common_output_cfg.setdefault(key, default_val)

        # Process 'logging'
        logging_cfg: LoggingConfigDict = common_cfg.setdefault("logging", {})
        logging_defaults = common_schema_props.get("logging", {}).get("default", {})
        for key, default_val in logging_defaults.items():
            logging_cfg.setdefault(key, default_val)
        self._ensure_directory_exists(logging_cfg.get("log_dir"), "logging directory", DEFAULT_LOG_DIR)

        # Process 'cache_settings'
        cache_cfg: CacheSettingsDict = common_cfg.setdefault("cache_settings", {})
        cache_defaults = common_schema_props.get("cache_settings", {}).get("default", {})
        for key, default_val in cache_defaults.items():
            cache_cfg.setdefault(key, default_val)
        self._ensure_directory_exists(cache_cfg.get("llm_cache_file"), "LLM cache file", DEFAULT_LLM_CACHE_FILE)

        # Process 'llm_default_options'
        llm_opts_cfg: LlmDefaultOptionsDict = common_cfg.setdefault("llm_default_options", {})
        llm_opts_defaults = common_schema_props.get("llm_default_options", {}).get("default", {})
        for key, default_val in llm_opts_defaults.items():
            llm_opts_cfg.setdefault(key, default_val)

    def _apply_defaults_to_analysis_section(self, section_key: str, section_schema: ConfigDict) -> None:
        """Apply default values from schema to a specific analysis section (code or web).

        Ensures the specified analysis section (e.g., 'code_analysis') and its
        sub-sections (e.g., 'source_options', 'diagram_generation') exist in
        `self._config_data`. If they or their fields are missing, default values
        from their respective schemas are applied.

        Args:
            section_key: The key of the analysis section in `self._config_data`
                         (e.g., "code_analysis", "web_analysis").
            section_schema: The JSON schema definition for this analysis section.
        """
        cfg = self._config_data
        analysis_cfg: ConfigDict = cfg.setdefault(section_key, {})  # Ensures the top-level section key exists
        analysis_schema_props = section_schema.get("properties", {})

        for sub_key, sub_schema_definition in analysis_schema_props.items():
            # If sub-key is missing and schema has a default for it
            if sub_key not in analysis_cfg and "default" in sub_schema_definition:
                analysis_cfg[sub_key] = copy.deepcopy(sub_schema_definition["default"])
            # If sub-key is missing and it's supposed to be an object, create an empty one
            elif sub_key not in analysis_cfg and sub_schema_definition.get("type") == "object":
                analysis_cfg[sub_key] = {}
            # If sub-key exists and is an object, and schema has defaults for its properties
            elif isinstance(analysis_cfg.get(sub_key), dict) and "default" in sub_schema_definition:
                # This handles cases where a sub-object (like 'diagram_generation') itself has a default block
                # in the schema, and we need to merge these defaults into the existing sub-object.
                current_sub_object_cfg: ConfigDict = analysis_cfg[sub_key]
                default_values_for_sub_object: ConfigDict = sub_schema_definition["default"]
                for def_k, def_v in default_values_for_sub_object.items():
                    current_sub_object_cfg.setdefault(def_k, def_v)
            # This also needs to handle nested objects within the sub_key, like sequence_diagrams
            elif isinstance(analysis_cfg.get(sub_key), dict) and "properties" in sub_schema_definition:
                # Recursively apply defaults for nested objects if necessary, or handle explicitly
                nested_obj_cfg: ConfigDict = analysis_cfg[sub_key]
                nested_obj_schema_props = sub_schema_definition.get("properties", {})
                for nested_prop_key, nested_prop_schema in nested_obj_schema_props.items():
                    if nested_prop_key not in nested_obj_cfg and "default" in nested_prop_schema:
                        nested_obj_cfg[nested_prop_key] = copy.deepcopy(nested_prop_schema["default"])

    def _resolve_value_from_env(self, env_var_name: Optional[str], value_purpose: str) -> Optional[str]:
        """Resolve a value from an environment variable.

        If `env_var_name` is provided and the corresponding environment variable
        is set and non-empty, its value is returned. Otherwise, None is returned.

        Args:
            env_var_name: The name of the environment variable to look up.
                          If None or empty, the function returns None.
            value_purpose: A string describing what this value is for (e.g., "GitHub token"),
                           used for logging.

        Returns:
            The string value of the environment variable if found and non-empty,
            otherwise None.
        """
        if env_var_name and isinstance(env_var_name, str) and env_var_name.strip():
            env_val = os.environ.get(env_var_name.strip())
            if env_val:  # Check if not None and not empty string
                logger.info("Loaded %s from environment variable '%s'.", value_purpose, env_var_name)
                return env_val
            logger.debug("Environment variable '%s' for %s not set or is empty.", env_var_name, value_purpose)
        elif env_var_name:  # If env_var_name was provided but was e.g. an empty string after strip
            logger.debug("Invalid environment variable name provided for %s: '%s'", value_purpose, env_var_name)
        return None

    def _resolve_github_token(self) -> Optional[str]:
        """Resolve the GitHub token.

        It first checks for a token directly specified in `code_analysis.github_token`.
        If not found or is null/empty, it attempts to load it from the environment
        variable specified in `code_analysis.github_token_env_var`.

        Returns:
            The resolved GitHub token as a string, or None if not found or configured.
        """
        code_analysis_cfg: ConfigDict = self._config_data.get("code_analysis", {})
        direct_token_val: Any = code_analysis_cfg.get("github_token")
        direct_token: Optional[str] = str(direct_token_val) if isinstance(direct_token_val, str) else None

        if direct_token and direct_token.strip():
            logger.info("Using GitHub token directly from 'code_analysis.github_token'.")
            return direct_token

        env_var_name_val: Any = code_analysis_cfg.get("github_token_env_var")
        env_var_name: Optional[str] = str(env_var_name_val) if isinstance(env_var_name_val, str) else None
        return self._resolve_value_from_env(env_var_name, "GitHub token")

    def _resolve_llm_profile_settings(self, llm_profile: LlmProfileDict) -> None:
        """Resolve API key and Vertex AI settings for a given LLM profile.

        This method modifies the `llm_profile` dictionary in-place.
        For API keys, it first checks `llm_profile["api_key"]`. If null or empty,
        it uses `llm_profile["api_key_env_var"]` to get the key from `os.environ`.
        Similar logic is applied for Vertex AI's `vertex_project` and `vertex_location`.

        Args:
            llm_profile: The LLM profile dictionary to process.
                         Expected to be a deep copy if modification is not desired on original.

        Raises:
            ConfigError: If Vertex AI specific settings (project or location) are
                         required but not found either directly in the profile or
                         via their specified environment variables.
        """
        provider_id = str(llm_profile.get("provider_id", "unknown_provider"))

        # Resolve API Key
        if not llm_profile.get("api_key"):  # If api_key is not directly set or is null/empty
            api_key_env_var_val: Any = llm_profile.get("api_key_env_var")
            api_key_env_var: Optional[str] = str(api_key_env_var_val) if isinstance(api_key_env_var_val, str) else None
            api_key_from_env = self._resolve_value_from_env(api_key_env_var, f"API key for LLM profile '{provider_id}'")
            if api_key_from_env:
                llm_profile["api_key"] = api_key_from_env
            elif not llm_profile.get("is_local_llm") and llm_profile.get("provider") != "vertexai":
                logger.warning(
                    "API key for cloud LLM profile '%s' (provider: %s) not found in config or env var '%s'. "
                    "Functionality may be limited.",
                    provider_id,
                    llm_profile.get("provider"),
                    api_key_env_var,
                )

        # Resolve Vertex AI specific settings
        if llm_profile.get("provider") == "vertexai":
            if not llm_profile.get("vertex_project"):
                vertex_project_env_var_val: Any = llm_profile.get("vertex_project_env_var")
                vertex_project_env_var: Optional[str] = (
                    str(vertex_project_env_var_val) if isinstance(vertex_project_env_var_val, str) else None
                )

                vertex_project_from_env = self._resolve_value_from_env(
                    vertex_project_env_var, f"Vertex project for LLM profile '{provider_id}'"
                )
                if vertex_project_from_env:
                    llm_profile["vertex_project"] = vertex_project_from_env
                else:
                    msg = (
                        f"Vertex AI project missing for profile '{provider_id}' (checked direct config "
                        f"and env var: '{vertex_project_env_var}')."
                    )
                    logger.error(msg)
                    raise ConfigError(msg)

            if not llm_profile.get("vertex_location"):
                vertex_location_env_var_val: Any = llm_profile.get("vertex_location_env_var")
                vertex_location_env_var: Optional[str] = (
                    str(vertex_location_env_var_val) if isinstance(vertex_location_env_var_val, str) else None
                )
                vertex_location_from_env = self._resolve_value_from_env(
                    vertex_location_env_var, f"Vertex location for LLM profile '{provider_id}'"
                )
                if vertex_location_from_env:
                    llm_profile["vertex_location"] = vertex_location_from_env
                else:
                    msg = (
                        f"Vertex AI location missing for profile '{provider_id}' (checked direct config "
                        f"and env var: '{vertex_location_env_var}')."
                    )
                    logger.error(msg)
                    raise ConfigError(msg)

    def _get_active_llm_config(self, active_llm_provider_id: str) -> LlmProfileDict:
        """Retrieve and process the configuration for the specified active LLM provider.

        Finds the LLM profile matching `active_llm_provider_id`, resolves its
        API key and any provider-specific settings (like Vertex AI project/location)
        from environment variables if necessary, and then merges these with the
        common LLM default options (e.g., retries, wait times).

        Args:
            active_llm_provider_id: The `provider_id` of the LLM profile to activate.

        Returns:
            A dictionary representing the fully resolved configuration for the
            active LLM provider.

        Raises:
            ConfigError: If the specified `active_llm_provider_id` is not found
                         in the `profiles.llm_profiles` list, or if required
                         settings for that provider (e.g., Vertex AI project)
                         cannot be resolved.
        """
        profiles_cfg: ConfigDict = self._config_data.get("profiles", {})
        llm_profiles_list_val: Any = profiles_cfg.get("llm_profiles", [])
        llm_profiles: list[LlmProfileDict] = llm_profiles_list_val if isinstance(llm_profiles_list_val, list) else []

        active_llm_profile_orig: Optional[LlmProfileDict] = next(
            (p for p in llm_profiles if isinstance(p, dict) and p.get("provider_id") == active_llm_provider_id), None
        )
        if not active_llm_profile_orig:
            msg = f"Active LLM provider_id '{active_llm_provider_id}' not found in profiles.llm_profiles."
            raise ConfigError(msg)

        # Work on a deep copy to avoid modifying the original _config_data structure during resolution
        active_llm_profile = copy.deepcopy(active_llm_profile_orig)
        self._resolve_llm_profile_settings(active_llm_profile)  # Modifies active_llm_profile in-place

        common_section: ConfigDict = self._config_data.get("common", {})
        llm_default_opts_val: Any = common_section.get("llm_default_options", {})
        common_llm_opts: LlmDefaultOptionsDict = llm_default_opts_val if isinstance(llm_default_opts_val, dict) else {}

        # Merge common defaults with the specific active profile; profile settings take precedence
        final_llm_config: LlmProfileDict = {**common_llm_opts, **active_llm_profile}
        return final_llm_config

    def _process_code_analysis_config(self) -> None:
        """Process and resolve the 'code_analysis' configuration section.

        If code analysis is enabled, this method resolves the GitHub token,
        finds the active language profile, merges it with common source options,
        and determines the active LLM configuration for code analysis.
        The resolved settings are stored in `self._config_data["code_analysis_resolved"]`.
        If disabled, a minimal entry indicating this is stored.

        Raises:
            ConfigError: If required IDs (language profile, LLM provider) are missing
                         or not found in their respective profile lists.
        """
        code_analysis_cfg_orig: ConfigDict = self._config_data.get("code_analysis", {})
        if not code_analysis_cfg_orig.get("enabled", False):  # Default is from schema if key missing
            logger.info("Code analysis is disabled in configuration.")
            self._config_data["code_analysis_resolved"] = {"enabled": False}
            return

        resolved_github_token = self._resolve_github_token()

        profiles_cfg: ConfigDict = self._config_data.get("profiles", {})
        lang_profiles_list_val: Any = profiles_cfg.get("language_profiles", [])
        language_profiles: list[LanguageProfileDict] = (
            lang_profiles_list_val if isinstance(lang_profiles_list_val, list) else []
        )
        active_lang_profile_id_val: Any = code_analysis_cfg_orig.get("active_language_profile_id")
        active_lang_profile_id: Optional[str] = (
            str(active_lang_profile_id_val) if isinstance(active_lang_profile_id_val, str) else None
        )

        if not active_lang_profile_id:
            raise ConfigError("Missing 'active_language_profile_id' in 'code_analysis' section.")

        active_lang_profile: Optional[LanguageProfileDict] = next(
            (p for p in language_profiles if isinstance(p, dict) and p.get("profile_id") == active_lang_profile_id),
            None,
        )
        if not active_lang_profile:
            raise ConfigError(f"Lang profile ID '{active_lang_profile_id}' not found in profiles.language_profiles.")

        source_options_val: Any = code_analysis_cfg_orig.get("source_options", {})
        source_options_base: SourceOptionsDict = source_options_val if isinstance(source_options_val, dict) else {}
        # Merge base source_options with active language profile; profile settings take precedence
        resolved_source_config: ConfigDict = {**source_options_base, **active_lang_profile}

        active_llm_id_code_val: Any = code_analysis_cfg_orig.get("active_llm_provider_id")
        active_llm_id_code: Optional[str] = (
            str(active_llm_id_code_val) if isinstance(active_llm_id_code_val, str) else None
        )
        if not active_llm_id_code:
            raise ConfigError("Missing 'active_llm_provider_id' in 'code_analysis' section.")
        resolved_llm_config_code = self._get_active_llm_config(active_llm_id_code)

        self._config_data["code_analysis_resolved"] = ResolvedCodeAnalysisConfig(
            enabled=True,
            github_token=resolved_github_token,
            source_config=resolved_source_config,
            diagram_generation=code_analysis_cfg_orig.get("diagram_generation", {}),
            output_options=code_analysis_cfg_orig.get("output_options", {}),
            llm_config=resolved_llm_config_code,
        )
        logger.debug("Resolved code_analysis config: %s", self._config_data["code_analysis_resolved"])

    def _process_web_analysis_config(self) -> None:
        """Process and resolve the 'web_analysis' configuration section.

        If web analysis is enabled, this method determines the active LLM
        configuration for web tasks. The resolved settings are stored in
        `self._config_data["web_analysis_resolved"]`. If disabled, a minimal
        entry indicating this is stored.

        Raises:
            ConfigError: If the required `active_llm_provider_id` is missing
                         or not found in LLM profiles.
        """
        web_analysis_cfg_orig: ConfigDict = self._config_data.get("web_analysis", {})
        if not web_analysis_cfg_orig.get("enabled", False):  # Default is from schema if key missing
            logger.info("Web analysis is disabled in configuration.")
            self._config_data["web_analysis_resolved"] = {"enabled": False}
            return

        active_llm_id_web_val: Any = web_analysis_cfg_orig.get("active_llm_provider_id")
        active_llm_id_web: Optional[str] = (
            str(active_llm_id_web_val) if isinstance(active_llm_id_web_val, str) else None
        )

        if not active_llm_id_web:
            raise ConfigError("Missing 'active_llm_provider_id' in 'web_analysis' section.")
        resolved_llm_config_web = self._get_active_llm_config(active_llm_id_web)

        self._config_data["web_analysis_resolved"] = ResolvedWebAnalysisConfig(
            enabled=True,
            crawler_options=web_analysis_cfg_orig.get("crawler_options", {}),
            output_options=web_analysis_cfg_orig.get("output_options", {}),
            llm_config=resolved_llm_config_web,
        )
        logger.debug("Resolved web_analysis config: %s", self._config_data["web_analysis_resolved"])

    def process(self) -> ConfigDict:
        """Load, validate, and process the entire application configuration.

        This is the main public method of the `ConfigLoader`. It orchestrates
        reading the config file, validating its schema, applying default values
        to all sections, and then processing the `code_analysis` and `web_analysis`
        sections to resolve active profiles and environment-dependent settings.

        Returns:
            A `ConfigDict` containing the fully processed and resolved configuration.
            This dictionary has a top-level structure including 'common',
            'code_analysis' (resolved), 'web_analysis' (resolved), and
            'profiles_original'.

        Raises:
            FileNotFoundError: If the configuration file is not found.
            ConfigError: If there's an error in JSON syntax, schema validation,
                         or if required profile IDs are missing/invalid.
            ImportError: If `jsonschema` is required for validation but not installed.
            RuntimeError: For unexpected issues with `jsonschema` components.
        """
        logger.info("Loading configuration from: %s", self._config_path)
        self._read_config_file()
        self._validate_schema()

        self._apply_defaults_and_populate_common()
        self._apply_defaults_to_analysis_section("code_analysis", CODE_ANALYSIS_SCHEMA)
        self._apply_defaults_to_analysis_section("web_analysis", WEB_ANALYSIS_SCHEMA)

        self._process_code_analysis_config()
        self._process_web_analysis_config()

        final_config_to_return: ConfigDict = {
            "common": self._config_data.get("common", {}),
            "code_analysis": self._config_data.get("code_analysis_resolved", {"enabled": False}),
            "web_analysis": self._config_data.get("web_analysis_resolved", {"enabled": False}),
            "profiles_original": self._config_data.get("profiles", {}),  # For inspection or dynamic use
        }

        logger.info("Configuration loaded and processed successfully.")
        if logger.isEnabledFor(logging.DEBUG):
            try:
                log_config_copy = json.loads(json.dumps(final_config_to_return))
                # Redact sensitive info from resolved sections for logging
                code_analysis_log = log_config_copy.get("code_analysis", {})
                if isinstance(code_analysis_log.get("llm_config"), dict):
                    code_analysis_log["llm_config"]["api_key"] = "***REDACTED***"
                if "github_token" in code_analysis_log:  # github_token is top-level in resolved
                    code_analysis_log["github_token"] = "***REDACTED***"

                web_analysis_log = log_config_copy.get("web_analysis", {})
                if isinstance(web_analysis_log.get("llm_config"), dict):
                    web_analysis_log["llm_config"]["api_key"] = "***REDACTED***"

                logger.debug("Final processed config data: %s", json.dumps(log_config_copy, indent=2))
            except (TypeError, ValueError) as dump_error:
                logger.debug("Could not serialize final config for debug logging: %s", dump_error)

        return final_config_to_return


def load_config(config_path_str: str = "config.json") -> ConfigDict:
    """Load, validate, process, and return the application configuration.

    This is a convenience function that instantiates and uses the `ConfigLoader`
    class to perform the comprehensive configuration loading and processing tasks.

    Args:
        config_path_str (str): The path string to the JSON configuration file.
                               Defaults to "config.json" in the current working directory.

    Returns:
        A `ConfigDict` representing the fully processed, validated, and resolved
        application configuration, ready for use by other parts of the application.

    Raises:
        ConfigError: If any step of configuration loading, schema validation,
                     or processing (e.g., resolving active profiles, environment
                     variables) fails.
        FileNotFoundError: If the specified configuration file is not found.
        ImportError: If the `jsonschema` library (a dependency for schema
                     validation) is required but not installed.
    """
    loader = ConfigLoader(config_path_str)
    return loader.process()


# End of src/sourcelens/config.py
