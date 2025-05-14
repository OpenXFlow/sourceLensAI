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

"""Utilities for validating data structures, particularly YAML output from LLMs.

Includes functions to extract YAML blocks from strings and validate them
against expected types (list, dictionary) and optional JSON schemas.
Requires PyYAML and optionally jsonschema.
"""

import logging
import re
from typing import Any, Final, Optional

from typing_extensions import TypeAlias

YAML_AVAILABLE = False
yaml_module_global: Optional[Any] = None  # Use a different name to avoid conflict with 'yaml' type
SafeLoader_global: Optional[Any] = None
YAMLErrorType_global: Optional[type[Exception]] = None

try:
    import yaml as imported_yaml_module
    from yaml import CSafeLoader as ImportedCSafeLoader  # type: ignore[import-untyped]

    yaml_module_global = imported_yaml_module
    SafeLoader_global = ImportedCSafeLoader
    YAMLErrorType_global = imported_yaml_module.YAMLError
    YAML_AVAILABLE = True
except ImportError:
    try:
        import yaml as imported_yaml_module_fb  # type: ignore[no-redef]
        from yaml import SafeLoader as ImportedSafeLoader_fb  # type: ignore[no-redef]

        yaml_module_global = imported_yaml_module_fb
        SafeLoader_global = ImportedSafeLoader_fb
        YAMLErrorType_global = imported_yaml_module_fb.YAMLError
        YAML_AVAILABLE = True
    except ImportError:
        YAML_AVAILABLE = False


JSONSCHEMA_AVAILABLE = False
jsonschema_validate_global: Optional[Any] = None
JsonSchemaValidationErrorType_global: Optional[type[Exception]] = None

try:
    from jsonschema import validate as imported_jsonschema_validate
    from jsonschema.exceptions import ValidationError as ImportedJsonSchemaValidationError

    jsonschema_validate_global = imported_jsonschema_validate
    JsonSchemaValidationErrorType_global = ImportedJsonSchemaValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


logger: logging.Logger = logging.getLogger(__name__)

YAML_BLOCK_REGEX_PATTERN: Final[str] = r"```(?:yaml|yml)?\s*\n(.*?)\n```"
YAML_BLOCK_REGEX: Final[re.Pattern[str]] = re.compile(YAML_BLOCK_REGEX_PATTERN, re.DOTALL | re.IGNORECASE)
MAX_SNIPPET_LEN: Final[int] = 200

JsonSchemaType: TypeAlias = Optional[dict[str, Any]]
YamlData: TypeAlias = Any


class ValidationFailure(ValueError):
    """Custom exception raised when LLM response validation fails."""

    def __init__(self, message: str, raw_output: Optional[str] = None) -> None:
        """Initialize ValidationFailure exception.

        Args:
            message: The core error message.
            raw_output: Optional raw LLM output string for context in logs.
        """
        self.raw_output = raw_output
        full_message = f"Validation Failed: {message}"
        if raw_output:
            snippet_len = min(len(raw_output), MAX_SNIPPET_LEN)
            snippet = raw_output[:snippet_len] + ("..." if len(raw_output) > snippet_len else "")
            logger.debug("Validation failure related raw output snippet:\n---\n%s\n---", snippet)
        super().__init__(full_message)


def _ensure_yaml_available() -> None:
    """Raise ImportError if PyYAML library is not available or SafeLoader is missing."""
    if not YAML_AVAILABLE or yaml_module_global is None or SafeLoader_global is None or YAMLErrorType_global is None:
        raise ImportError("The 'PyYAML' library, SafeLoader and YAMLError are required. Please install it.")


def _ensure_jsonschema_available() -> None:
    """Raise ImportError if jsonschema library or its core components are not available."""
    if not JSONSCHEMA_AVAILABLE or jsonschema_validate_global is None or JsonSchemaValidationErrorType_global is None:
        raise ImportError("The 'jsonschema' library and ValidationError are required. Please install it.")


def _extract_yaml_block(raw_string: str) -> Optional[str]:
    """Extract the first YAML code block from a string.

    Searches for blocks fenced by ```yaml, ```yml, or just ```.
    If no fences are found, attempts to parse the whole string if it looks like YAML.

    Args:
        raw_string: The input string, typically from an LLM response.

    Returns:
        The extracted YAML content as a string, or None if no suitable block is found.
    """
    if not isinstance(raw_string, str):
        logger.warning("Input to _extract_yaml_block was not a string, got: %s", type(raw_string).__name__)
        return None
    match = YAML_BLOCK_REGEX.search(raw_string)
    if match:
        return match.group(1).strip()

    stripped_string = raw_string.strip()
    if stripped_string.startswith(("-", "{")) or re.match(r"^\s*[\w.-]+:", stripped_string):
        logger.debug("No YAML fences found, attempting to parse entire string as YAML.")
        return stripped_string

    logger.warning("Could not find YAML code fences in the LLM response, and string does not appear to be raw YAML.")
    return None


def _validate_with_jsonschema(instance: YamlData, schema: dict[str, Any], context_description: str) -> None:
    """Validate data against a JSON schema using the jsonschema library.

    Args:
        instance: The data instance to validate (parsed from YAML).
        schema: The JSON schema dictionary to validate against.
        context_description: A string describing the context of validation.

    Raises:
        ValidationFailure: If schema validation fails or an unexpected jsonschema error occurs.
        ImportError: If the jsonschema library is not installed.
    """
    _ensure_jsonschema_available()
    assert jsonschema_validate_global is not None and JsonSchemaValidationErrorType_global is not None

    try:
        jsonschema_validate_global(instance=instance, schema=schema)
        logger.debug("YAML %s passed schema validation.", context_description)
    except JsonSchemaValidationErrorType_global as e_schema:
        relative_path_val: Any = getattr(e_schema, "relative_path", [])
        path_str = " -> ".join(map(str, relative_path_val)) if relative_path_val else "root"
        message_val: str = getattr(e_schema, "message", str(e_schema))
        msg = f"YAML {context_description} failed schema validation at '{path_str}': {message_val}"

        instance_val: Any = getattr(e_schema, "instance", "N/A")
        instance_repr = repr(instance_val)
        if len(instance_repr) > MAX_SNIPPET_LEN:
            instance_repr = instance_repr[:MAX_SNIPPET_LEN] + "..."
        logger.debug("Instance causing schema failure ('%s' in %s):\n%s", path_str, context_description, instance_repr)
        raise ValidationFailure(msg) from e_schema
    except Exception as e_generic:
        msg = f"Unexpected error during YAML {context_description} schema validation: {e_generic!s}"
        raise ValidationFailure(msg) from e_generic


def validate_yaml_list(
    raw_llm_output: str, item_schema: JsonSchemaType = None, list_schema: JsonSchemaType = None
) -> list[Any]:
    """Extract, parse, and optionally validate a YAML list from LLM output.

    Args:
        raw_llm_output: The raw string response from the LLM.
        item_schema: An optional JSON schema to validate *each item* in the list.
        list_schema: An optional JSON schema to validate the *list itself*.

    Returns:
        The list parsed from the YAML block. If `item_schema` is provided,
        only items conforming to it are included.

    Raises:
        ValidationFailure: If YAML parsing fails, the root object is not a list,
                           or if `list_schema` validation fails.
        ImportError: If required libraries are not installed.
    """
    _ensure_yaml_available()
    yaml_str = _extract_yaml_block(raw_llm_output)
    if yaml_str is None:
        raise ValidationFailure("No YAML block found in the LLM output.", raw_llm_output)

    parsed_data: YamlData
    try:
        assert yaml_module_global is not None and SafeLoader_global is not None and YAMLErrorType_global is not None
        parsed_data = yaml_module_global.load(yaml_str, Loader=SafeLoader_global)
    except Exception as e:  # Catch all exceptions, then check type
        if YAMLErrorType_global is not None and isinstance(e, YAMLErrorType_global):
            snippet_len = min(len(yaml_str), MAX_SNIPPET_LEN)
            snippet = yaml_str[:snippet_len] + ("..." if len(yaml_str) > snippet_len else "")
            logger.debug("Invalid YAML snippet:\n---\n%s\n---", snippet)
            raise ValidationFailure(f"Invalid YAML syntax: {e!s}", raw_llm_output) from e
        else:
            raise
    # Removed the broad except Exception here as _ensure_yaml_available should have caught import issues

    if not isinstance(parsed_data, list):
        raise ValidationFailure(f"Expected YAML list, got {type(parsed_data).__name__}.", raw_llm_output)

    if list_schema:
        _validate_with_jsonschema(parsed_data, list_schema, "list structure")

    if item_schema:
        validated_list_items: list[Any] = []
        for i, item in enumerate(list(parsed_data)):
            try:
                _validate_with_jsonschema(item, item_schema, f"list item at index {i}")
                validated_list_items.append(item)
            except ValidationFailure as e_item_schema:
                logger.warning(
                    "Skipping list item %d due to item-level schema validation failure: %s", i, e_item_schema
                )
        logger.debug("Validated %d/%d items against item-level schema.", len(validated_list_items), len(parsed_data))
        return validated_list_items
    return parsed_data


def validate_yaml_dict(raw_llm_output: str, dict_schema: JsonSchemaType = None) -> dict[str, Any]:
    """Extract, parse, and optionally validate a YAML dictionary from LLM output.

    Args:
        raw_llm_output: The raw string response from the LLM.
        dict_schema: An optional JSON schema dictionary to validate the dictionary structure.

    Returns:
        The validated dictionary parsed from the YAML block.

    Raises:
        ValidationFailure: If YAML parsing fails, the root object is not a dictionary,
                           or if `dict_schema` validation fails.
        ImportError: If required libraries are not installed.
    """
    _ensure_yaml_available()
    yaml_str = _extract_yaml_block(raw_llm_output)
    if yaml_str is None:
        raise ValidationFailure("No YAML block found in the LLM output.", raw_llm_output)

    parsed_data: YamlData
    try:
        assert yaml_module_global is not None and SafeLoader_global is not None and YAMLErrorType_global is not None
        parsed_data = yaml_module_global.load(yaml_str, Loader=SafeLoader_global)
    except Exception as e:  # Use Exception, then check type
        if YAMLErrorType_global is not None and isinstance(e, YAMLErrorType_global):
            snippet_len = min(len(yaml_str), MAX_SNIPPET_LEN)
            snippet = yaml_str[:snippet_len] + ("..." if len(yaml_str) > snippet_len else "")
            logger.debug("Invalid YAML snippet:\n---\n%s\n---", snippet)
            raise ValidationFailure(f"Invalid YAML syntax: {e!s}", raw_llm_output) from e
        else:
            raise
    # Removed the broad except Exception here

    if not isinstance(parsed_data, dict):
        msg = f"Expected a YAML dictionary/mapping, but got type {type(parsed_data).__name__}."
        raise ValidationFailure(msg, raw_llm_output)

    if dict_schema:
        _validate_with_jsonschema(parsed_data, dict_schema, "dictionary structure")

    return parsed_data  # type: ignore[return-value]


# End of src/sourcelens/utils/validation.py
