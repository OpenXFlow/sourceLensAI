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

"""Handles API calls to local LLM servers, specifically those exposing an
OpenAI-compatible API endpoint.
"""

import json
import logging
from typing import Any, Optional  # Added Optional

from typing_extensions import TypeAlias

from ._exceptions import LlmApiError

REQUESTS_AVAILABLE = False
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None  # type: ignore[assignment]

LlmConfigDict: TypeAlias = dict[str, Any]
HeadersDict: TypeAlias = dict[str, str]
OpenAIPayload: TypeAlias = dict[str, Any]  # Specific for OpenAI-like payloads
ApiResponseChoices: TypeAlias = list[dict[str, Any]]
ApiResponseMessage: TypeAlias = dict[str, Any]


logger: logging.Logger = logging.getLogger(__name__)
REQUEST_TIMEOUT: int = 90  # Standard timeout in seconds


def _validate_local_llm_request_config(llm_config: LlmConfigDict) -> tuple[str, str]:
    """Validate and extract essential configuration for a local LLM request.

    Args:
        llm_config: The LLM configuration dictionary. Expected to contain
                    'api_base_url' and 'model'.

    Returns:
        A tuple containing the API base URL and the model name.

    Raises:
        ValueError: If 'api_base_url' or 'model' is missing or invalid.
    """
    api_base_url_any: Any = llm_config.get("api_base_url")
    model_name_any: Any = llm_config.get("model")

    if not api_base_url_any or not isinstance(api_base_url_any, str):
        raise ValueError("Missing or invalid 'api_base_url' for local LLM.")
    if not model_name_any or not isinstance(model_name_any, str):
        raise ValueError("Missing or invalid 'model' name for local LLM.")
    return str(api_base_url_any), str(model_name_any)


def _prepare_local_llm_payload(prompt: str, model_name: str) -> OpenAIPayload:
    """Prepare the JSON payload for an OpenAI-compatible local LLM.

    Args:
        prompt: The user prompt string.
        model_name: The name of the model to use.

    Returns:
        A dictionary representing the JSON payload for the API request.
    """
    return {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,  # Assuming non-streaming for now
    }


def _process_local_llm_response(response_data: dict[str, Any], status_code: int) -> str:
    """Process the JSON response from an OpenAI-compatible local LLM.

    Extracts the content from the first choice's message.

    Args:
        response_data: The parsed JSON dictionary from the API response.
        status_code: The HTTP status code of the response.

    Returns:
        The extracted text content from the LLM's response.

    Raises:
        LlmApiError: If the response structure is invalid or content is missing.
    """
    choices_any: Any = response_data.get("choices")
    if not isinstance(choices_any, list) or not choices_any:
        error_msg = "Invalid/empty 'choices' in local LLM response."
        raise LlmApiError(error_msg, status_code, "local_openai_compatible")
    choices: ApiResponseChoices = choices_any  # type: ignore[assignment]

    message_any: Any = choices[0].get("message")
    if not isinstance(message_any, dict) or "content" not in message_any:
        error_msg = "Invalid/missing 'message' in local LLM choice."
        raise LlmApiError(error_msg, status_code, "local_openai_compatible")
    message: ApiResponseMessage = message_any

    response_text_any: Any = message["content"]
    if not isinstance(response_text_any, str):
        error_msg = "Invalid content type from local LLM."
        raise LlmApiError(error_msg, status_code, "local_openai_compatible")
    response_text: str = response_text_any

    if not response_text:  # Log if successful but empty
        logger.warning("Local LLM call succeeded but returned empty response content.")
    return response_text


def call_local_openai_compatible(prompt: str, llm_config: LlmConfigDict) -> str:
    """Handle API call to a local OpenAI-compatible server.

    Args:
        prompt: The prompt string to send to the LLM.
        llm_config: Dictionary containing LLM provider configuration,
                    including 'api_base_url' and 'model'.

    Returns:
        The text response from the LLM.

    Raises:
        ImportError: If the 'requests' library is not installed.
        RuntimeError: If the 'requests' library failed to import correctly.
        ValueError: If essential configuration ('api_base_url', 'model') is missing.
        LlmApiError: For API request failures (e.g., connection error, HTTP error)
                     or issues parsing the LLM response.
    """
    if not REQUESTS_AVAILABLE:
        raise ImportError("The 'requests' library is required for local LLM calls.")
    if requests is None:
        raise RuntimeError("Requests library failed to import correctly despite availability check.")

    api_base_url, model_name = _validate_local_llm_request_config(llm_config)
    payload = _prepare_local_llm_payload(prompt, model_name)
    headers: HeadersDict = {"Content-Type": "application/json"}
    endpoint_url = f"{api_base_url.rstrip('/')}/chat/completions"

    logger.debug("Local LLM Request URL: %s", endpoint_url)
    logger.debug("Local LLM Request Payload: %s", json.dumps(payload))

    try:
        response = requests.post(endpoint_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
        response_data: dict[str, Any] = response.json()
        return _process_local_llm_response(response_data, response.status_code)

    except requests.exceptions.ConnectionError as e:
        error_msg = f"Could not connect to local LLM server at {api_base_url}. Is it running?"
        raise LlmApiError(error_msg, provider="local_openai_compatible") from e
    except requests.exceptions.HTTPError as e_http:  # Catch HTTPError from raise_for_status
        status_code_val = e_http.response.status_code if e_http.response is not None else None
        status_code: Optional[int] = status_code_val if isinstance(status_code_val, int) else None
        error_detail = str(e_http)
        if e_http.response is not None:
            try:
                err_resp_json: dict[str, Any] = e_http.response.json()
                # Try to get a more specific error message from the JSON response
                error_detail = err_resp_json.get("error", {}).get("message", e_http.response.text)
            except json.JSONDecodeError:  # Fallback if response is not JSON
                error_detail = e_http.response.text
        error_msg = f"Local LLM API request failed: {error_detail}"
        raise LlmApiError(error_msg, status_code, "local_openai_compatible") from e_http
    except requests.exceptions.RequestException as e:  # Catch other request-related errors
        # This block might be redundant if HTTPError catches most relevant cases from requests.post
        # However, it's kept for other potential RequestException types.
        error_msg = f"Local LLM API request failed with general RequestException: {e!s}"
        raise LlmApiError(error_msg, provider="local_openai_compatible") from e
    except LlmApiError:  # Re-raise LlmApiError from _process_local_llm_response
        raise
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e_parse:  # Catch parsing errors from our side
        error_msg = f"Failed to parse local LLM response or invalid structure: {e_parse!s}"
        raise LlmApiError(error_msg, provider="local_openai_compatible") from e_parse


# End of src/sourcelens/utils/_local_llm_api.py
