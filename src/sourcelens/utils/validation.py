"""Utilities for validating data structures, particularly YAML output from LLMs.

Includes functions to extract YAML blocks from strings and validate them
against expected types (list, dictionary) and optional JSON schemas.
Requires PyYAML and optionally jsonschema.
"""

import logging
import re
from typing import Any, Optional, TypeAlias

# --- Safe YAML Import ---
YAML_AVAILABLE = False
try:
    import yaml
    try:
        # PGH003: Specific ignore for potential dynamic loading issue if CLoader not built
        from yaml import CSafeLoader as SafeLoader  # type: ignore[import-untyped, no-redef]
    except ImportError:
        # Fallback to the pure Python SafeLoader
        from yaml import SafeLoader  # type: ignore[import-untyped, no-redef]
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    SafeLoader = None
    YAML_AVAILABLE = False

# --- Safe JSON Schema Import ---
JSONSCHEMA_AVAILABLE = False
try:
    # PGH003: Specific ignore for potential dynamic loading issue
    from jsonschema import validate as jsonschema_validate
    from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema_validate = None
    JsonSchemaValidationError = None
    JSONSCHEMA_AVAILABLE = False


logger = logging.getLogger(__name__)

# --- Constants ---
# Regex to find YAML block, allows optional language specifier (e.g., ```yaml)
YAML_BLOCK_REGEX = r"```(?:yaml|yml)?\s*\n(.*?)\n```"
# Define MAX_SNIPPET_LEN constant for PLR2004
MAX_SNIPPET_LEN = 200

# Type Aliases
JsonSchema: TypeAlias = Optional[dict[str, Any]]
YamlData: TypeAlias = Any # Type returned by yaml.load can be anything

class ValidationFailure(ValueError):
    """Custom exception raised when LLM response validation fails."""

    # __init__ remains the same as previous correction
    def __init__(self, message: str, raw_output: Optional[str] = None) -> None:
        """Initialize ValidationFailure exception."""
        self.raw_output = raw_output
        full_message = f"Validation Failed: {message}"
        if raw_output:
             snippet = raw_output[:MAX_SNIPPET_LEN] + ('...' if len(raw_output) > MAX_SNIPPET_LEN else '')
             logger.debug("Validation failure related raw output snippet:\n---\n%s\n---", snippet)
        super().__init__(full_message)


def _ensure_yaml_available() -> None:
    """Raise ImportError if PyYAML library is not available."""
    if not YAML_AVAILABLE or yaml is None or SafeLoader is None:
        raise ImportError("The 'PyYAML' library is required for YAML parsing. Please install it.")

def _ensure_jsonschema_available() -> None:
    """Raise ImportError if jsonschema library is not available."""
    if not JSONSCHEMA_AVAILABLE or jsonschema_validate is None or JsonSchemaValidationError is None:
        raise ImportError("The 'jsonschema' library is required for schema validation. Please install it.")


def _extract_yaml_block(raw_string: str) -> Optional[str]:
    """Extract the first YAML code block (```yaml ... ``` or ```yml ...```) from a string."""
    # Logic remains the same as previous correction
    if not isinstance(raw_string, str): return None
    match = re.search(YAML_BLOCK_REGEX, raw_string, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    stripped_string = raw_string.strip()
    if stripped_string.startswith(('-', '{')) or re.match(r"^\s*[\w.-]+:", stripped_string):
         logger.debug("No YAML fences found, attempting to parse entire string as YAML.")
         return stripped_string
    logger.warning("Could not find YAML code fences in the LLM response.")
    return None


def _validate_with_jsonschema(instance: Any, schema: dict[str, Any], context: str) -> None:
    """Helper to validate data against a JSON schema if jsonschema is available."""
    # ANN401: instance type is Any because it comes from yaml.load
    _ensure_jsonschema_available()
    # Add assertion for type checker after availability check
    assert jsonschema_validate is not None and JsonSchemaValidationError is not None

    try:
        jsonschema_validate(instance=instance, schema=schema)
        logger.debug("YAML %s passed schema validation.", context)
    except JsonSchemaValidationError as e_schema:
        path_str = " -> ".join(map(str, e_schema.relative_path)) if e_schema.path else "root"
        msg = f"YAML {context} failed schema validation at '{path_str}': {e_schema.message}"
        logger.debug("Instance causing schema failure (%s):\n%s", path_str, e_schema.instance)
        raise ValidationFailure(msg) from e_schema
    except Exception as e_generic: # Catch other potential jsonschema errors
        msg = f"Unexpected error during YAML {context} schema validation: {e_generic}"
        raise ValidationFailure(msg) from e_generic


def validate_yaml_list(
    raw_llm_output: str,
    item_schema: JsonSchema = None,
    list_schema: JsonSchema = None
) -> list[Any]:
    """Extract, parse, and optionally validate a YAML list from LLM output.

    Args:
        raw_llm_output: The raw string response from the LLM.
        item_schema: A JSON schema to validate *each item* in the list.
        list_schema: A JSON schema to validate the *list itself*.

    Returns:
        The validated list parsed from the YAML block.

    Raises:
        ValidationFailure: If validation fails.
        ImportError: If required libraries are not installed.

    """
    # C901: Complexity reduced slightly by helper functions, still potentially high
    _ensure_yaml_available()
    yaml_str = _extract_yaml_block(raw_llm_output)
    if yaml_str is None:
        raise ValidationFailure("No YAML block found in the LLM output.", raw_llm_output)

    try:
        assert SafeLoader is not None # Ensure SafeLoader is available for type checker
        parsed_data: YamlData = yaml.load(yaml_str, Loader=SafeLoader)
    except yaml.YAMLError as e:
        snippet = yaml_str[:MAX_SNIPPET_LEN] + ('...' if len(yaml_str) > MAX_SNIPPET_LEN else '')
        logger.debug("Invalid YAML snippet:\n---\n%s\n---", snippet)
        raise ValidationFailure(f"Invalid YAML syntax: {e}", raw_llm_output) from e

    if not isinstance(parsed_data, list):
        raise ValidationFailure(f"Expected YAML list, got {type(parsed_data).__name__}.", raw_llm_output)

    if list_schema:
        _validate_with_jsonschema(parsed_data, list_schema, "list")

    if item_schema:
        validated_list = []
        items_to_validate = list(parsed_data)
        for i, item in enumerate(items_to_validate):
             try:
                 _validate_with_jsonschema(item, item_schema, f"list item {i}")
                 validated_list.append(item)
             except ValidationFailure as e_item_schema:
                 logger.warning("Skipping list item %d due to validation failure: %s", i, e_item_schema)
        logger.debug("Validated %d/%d items against item-level schema.", len(validated_list), len(items_to_validate))
        return validated_list # Return only validated items
    return parsed_data # Return original list if no item schema


def validate_yaml_dict(
    raw_llm_output: str,
    dict_schema: JsonSchema = None
) -> dict[str, Any]:
    """Extract, parse, and optionally validate a YAML dictionary from LLM output.

    Args:
        raw_llm_output: The raw string response from the LLM.
        dict_schema: A JSON schema dictionary to validate the dictionary structure.

    Returns:
        The validated dictionary parsed from the YAML block.

    Raises:
        ValidationFailure: If validation fails.
        ImportError: If required libraries are not installed.

    """
    _ensure_yaml_available()
    yaml_str = _extract_yaml_block(raw_llm_output)
    if yaml_str is None:
        raise ValidationFailure("No YAML block found in the LLM output.", raw_llm_output)

    try:
        assert SafeLoader is not None
        parsed_data: YamlData = yaml.load(yaml_str, Loader=SafeLoader)
    except yaml.YAMLError as e:
        snippet = yaml_str[:MAX_SNIPPET_LEN] + ('...' if len(yaml_str) > MAX_SNIPPET_LEN else '')
        logger.debug("Invalid YAML snippet:\n---\n%s\n---", snippet)
        raise ValidationFailure(f"Invalid YAML syntax: {e}", raw_llm_output) from e

    if not isinstance(parsed_data, dict):
        # Wrapped message for E501
        msg = (
            f"Expected a YAML dictionary/mapping, but got type "
            f"{type(parsed_data).__name__}."
        )
        raise ValidationFailure(msg, raw_llm_output)

    if dict_schema:
        _validate_with_jsonschema(parsed_data, dict_schema, "dictionary")

    # We know it's a dict here due to the isinstance check
    return parsed_data # type: ignore[return-value] # Type checker might not infer dict from check


# End of src/sourcelens/utils/validation.py
