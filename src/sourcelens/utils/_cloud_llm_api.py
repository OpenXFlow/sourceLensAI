# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Handles API calls to specific cloud-based LLM providers (Gemini, Perplexity, etc.).

This module contains the implementation details for interacting with each
supported cloud LLM service. It assumes configuration details (API keys, models)
are passed in via the llm_config dictionary.
"""

import json
import logging
from typing import Any, Optional  # Added Optional

from typing_extensions import TypeAlias

from ._exceptions import LlmApiError

GOOGLE_GENAI_AVAILABLE = False
try:
    from google import generativeai as genai
    from google.generativeai.types import (  # type: ignore[attr-defined]
        GenerationConfig,
        HarmBlockThreshold,
        HarmCategory,
    )

    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore[assignment]
    GenerationConfig = type("GenerationConfig", (), {})  # type: ignore[misc, assignment]
    HarmCategory = type("HarmCategory", (), {})  # type: ignore[misc, assignment]
    HarmBlockThreshold = type("HarmBlockThreshold", (), {})  # type: ignore[misc, assignment]

REQUESTS_AVAILABLE = False
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None  # type: ignore[assignment]

PERPLEXITY_API_URL: str = "https://api.perplexity.ai/chat/completions"
REQUEST_TIMEOUT: int = 90

LlmConfigDict: TypeAlias = dict[str, Any]
HeadersDict: TypeAlias = dict[str, str]
PerplexityPayload: TypeAlias = dict[str, Any]  # For Perplexity specific payload
PerplexityResponseChoices: TypeAlias = list[dict[str, Any]]
PerplexityResponseMessage: TypeAlias = dict[str, Any]


logger: logging.Logger = logging.getLogger(__name__)


def call_gemini(prompt: str, llm_config: LlmConfigDict) -> str:
    """Handle API call to Google Gemini.

    Args:
        prompt: The prompt string to send to the LLM.
        llm_config: Dictionary containing LLM provider configuration.

    Returns:
        The text response from the LLM.

    Raises:
        ImportError: If the Google Generative AI SDK is not installed.
        RuntimeError: If essential SDK components are not available.
        ValueError: If 'api_key' or 'model' is missing in llm_config.
        LlmApiError: For API call failures or blocked/empty responses.
    """
    if not GOOGLE_GENAI_AVAILABLE:
        raise ImportError("Google Generative AI SDK not installed.")
    if genai is None or HarmCategory is None or HarmBlockThreshold is None:  # type: ignore[truthy-bool]
        raise RuntimeError("Google GenAI SDK components failed import or are not available.")

    api_key_any: Any = llm_config.get("api_key")
    model_name_any: Any = llm_config.get("model")

    if not api_key_any or not isinstance(api_key_any, str):
        raise ValueError("Missing or invalid 'api_key' for Gemini provider.")
    if not model_name_any or not isinstance(model_name_any, str):
        raise ValueError("Missing or invalid 'model' for Gemini provider.")

    api_key: str = api_key_any
    model_name: str = model_name_any

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        raise LlmApiError(f"Failed to configure/initialize Gemini model: {e!s}", provider="gemini") from e

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,  # type: ignore[attr-defined]
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,  # type: ignore[attr-defined]
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,  # type: ignore[attr-defined]
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,  # type: ignore[attr-defined]
    }

    try:
        response = model.generate_content(prompt, safety_settings=safety_settings)
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            return "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, "text"))

        block_reason_val = (
            getattr(response.prompt_feedback, "block_reason", "Unknown") if response.prompt_feedback else "N/A"
        )
        finish_reason_val = (
            getattr(response.candidates[0], "finish_reason", "Unknown") if response.candidates else "N/A"
        )
        reason = str(finish_reason_val if finish_reason_val != "Unknown" else block_reason_val)
        raise LlmApiError(f"Gemini response empty/blocked. Reason: {reason}", provider="gemini")
    except Exception as e:
        raise LlmApiError(f"Gemini API call failed: {e!s}", provider="gemini") from e


def _validate_perplexity_config(llm_config: LlmConfigDict) -> tuple[str, str]:
    """Validate and extract API key and model for Perplexity.

    Args:
        llm_config: LLM configuration dictionary.

    Returns:
        A tuple of (api_key, model_name).

    Raises:
        ValueError: If 'api_key' or 'model' is missing or invalid.
    """
    api_key_any: Any = llm_config.get("api_key")
    model_name_any: Any = llm_config.get("model")

    if not api_key_any or not isinstance(api_key_any, str):
        raise ValueError("Missing or invalid 'api_key' for Perplexity provider.")
    if not model_name_any or not isinstance(model_name_any, str):
        raise ValueError("Missing or invalid 'model' for Perplexity provider.")
    return str(api_key_any), str(model_name_any)


def _prepare_perplexity_payload(prompt: str, model_name: str) -> PerplexityPayload:
    """Prepare the payload for the Perplexity API request.

    Args:
        prompt: The prompt string.
        model_name: The name of the Perplexity model.

    Returns:
        The payload dictionary.
    """
    return {"model": model_name, "messages": [{"role": "user", "content": prompt}]}


def _process_perplexity_response(response_data: dict[str, Any], status_code: int) -> str:
    """Process and extract content from Perplexity API JSON response.

    Args:
        response_data: The JSON response data from Perplexity.
        status_code: The HTTP status code of the response.

    Returns:
        The extracted text content.

    Raises:
        LlmApiError: If the response format is invalid.
    """
    choices_any: Any = response_data.get("choices")
    if not isinstance(choices_any, list) or not choices_any:
        error_msg = "Invalid/empty 'choices' in Perplexity response."
        raise LlmApiError(error_msg, status_code, "perplexity")
    choices: PerplexityResponseChoices = choices_any  # type: ignore[assignment]

    message_any: Any = choices[0].get("message")
    if not isinstance(message_any, dict) or "content" not in message_any:
        error_msg = "Invalid/missing 'message' in Perplexity choice."
        raise LlmApiError(error_msg, status_code, "perplexity")
    message: PerplexityResponseMessage = message_any

    response_text_any: Any = message["content"]
    if not isinstance(response_text_any, str):
        error_msg = "Invalid content type from Perplexity."
        raise LlmApiError(error_msg, status_code, "perplexity")
    return str(response_text_any)


def call_perplexity(prompt: str, llm_config: LlmConfigDict) -> str:
    """Handle API call to Perplexity AI.

    Args:
        prompt: The prompt string to send to the LLM.
        llm_config: Dictionary containing LLM provider configuration.

    Returns:
        The text response from the LLM.

    Raises:
        ImportError: If the 'requests' library is not installed.
        RuntimeError: If the 'requests' library failed to import correctly.
        ValueError: If 'api_key' or 'model' is missing in llm_config.
        LlmApiError: For API request failures or issues parsing the response.
    """
    if not REQUESTS_AVAILABLE:
        raise ImportError("The 'requests' library is not installed.")
    if requests is None:
        raise RuntimeError("Requests library failed to import correctly.")

    api_key, model_name = _validate_perplexity_config(llm_config)
    payload = _prepare_perplexity_payload(prompt, model_name)
    headers: HeadersDict = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response_data: dict[str, Any] = response.json()
        return _process_perplexity_response(response_data, response.status_code)
    except requests.exceptions.RequestException as e:
        status_code_val = e.response.status_code if e.response is not None else None
        status_code: Optional[int] = status_code_val if isinstance(status_code_val, int) else None
        error_detail = str(e)
        if e.response is not None:
            try:
                err_resp_json: dict[str, Any] = e.response.json()
                error_detail = err_resp_json.get("error", {}).get("message", e.response.text)
            except json.JSONDecodeError:
                error_detail = e.response.text
        raise LlmApiError(f"API request failed: {error_detail}", status_code, "perplexity") from e
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e_parse:  # LlmApiError is already caught
        raise LlmApiError(f"Failed to parse Perplexity response: {e_parse!s}", provider="perplexity") from e_parse


# Add functions for other cloud providers here...

# End of src/sourcelens/utils/_cloud_llm_api.py
