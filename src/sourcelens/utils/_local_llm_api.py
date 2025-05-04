"""Handles API calls to local LLM servers, specifically those exposing an
OpenAI-compatible API endpoint.
"""

import json
import logging
from typing import Any, TypeAlias

from ._exceptions import LlmApiError

REQUESTS_AVAILABLE = False
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None

LlmConfigDict: TypeAlias = dict[str, Any]
HeadersDict: TypeAlias = dict[str, str]

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 90


def call_local_openai_compatible(prompt: str, llm_config: LlmConfigDict) -> str:
    """Handle API call to a local OpenAI-compatible server."""
    if not REQUESTS_AVAILABLE:
        raise ImportError("The 'requests' library is required.")
    if requests is None: # Check added for type checker after safe import
        raise RuntimeError("Requests library failed to import correctly.")

    api_base_url = llm_config.get("api_base_url")
    model_name = llm_config.get("model")
    if not api_base_url or not isinstance(api_base_url, str):
        raise ValueError("Missing or invalid 'api_base_url'.")
    if not model_name:
        raise ValueError("Missing 'model' name.")

    endpoint_url = f"{api_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    headers: HeadersDict = { "Content-Type": "application/json" }

    logger.debug("Local LLM Request URL: %s", endpoint_url)
    logger.debug("Local LLM Request Payload: %s", json.dumps(payload))

    try:
        response = requests.post(endpoint_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response_data = response.json()

        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
             error_msg = "Invalid/empty 'choices' in local LLM response."
             raise LlmApiError(error_msg, response.status_code, "local_openai_compatible")

        message = choices[0].get("message")
        if not isinstance(message, dict) or "content" not in message:
             error_msg = "Invalid/missing 'message' in local LLM choice."
             raise LlmApiError(error_msg, response.status_code, "local_openai_compatible")

        response_text = message["content"]
        if not isinstance(response_text, str):
             error_msg = "Invalid content type from local LLM."
             raise LlmApiError(error_msg, response.status_code, "local_openai_compatible")

        if not response_text:
            logger.warning("Local LLM call succeeded but returned empty response.")

        return response_text

    except requests.exceptions.ConnectionError as e:
        error_msg = f"Could not connect to local LLM server at {api_base_url}. Is it running?"
        raise LlmApiError(error_msg, provider="local_openai_compatible") from e
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else None
        error_detail = str(e)
        if e.response is not None:
             try:
                 error_detail = e.response.json().get('error', {}).get('message', e.response.text)
             except json.JSONDecodeError:
                 error_detail = e.response.text
        error_msg = f"Local LLM API request failed: {error_detail}"
        raise LlmApiError(error_msg, status_code, "local_openai_compatible") from e
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e_parse:
         error_msg = f"Failed to parse local LLM response: {e_parse}"
         raise LlmApiError(error_msg, provider="local_openai_compatible") from e_parse

# End of src/sourcelens/utils/_local_llm_api.py
