"""Handles API calls to specific cloud-based LLM providers (Gemini, Perplexity, etc.).

This module contains the implementation details for interacting with each
supported cloud LLM service. It assumes configuration details (API keys, models)
are passed in via the llm_config dictionary.
"""

import json
import logging
from typing import Any, TypeAlias

# Import base error class from the new exceptions module
from ._exceptions import LlmApiError

# --- Safe SDK Imports ---
GOOGLE_GENAI_AVAILABLE = False
try:
    from google import generativeai as genai
    from google.generativeai.types import GenerationConfig, HarmBlockThreshold, HarmCategory
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    genai = None
    # Define dummy types if SDK is missing
    GenerationConfig = type("GenerationConfig", (), {})
    HarmCategory = type("HarmCategory", (), {})
    HarmBlockThreshold = type("HarmBlockThreshold", (), {})

REQUESTS_AVAILABLE = False
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None

# --- Constants ---
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
REQUEST_TIMEOUT = 90

# --- Type Aliases ---
LlmConfigDict: TypeAlias = dict[str, Any]
HeadersDict: TypeAlias = dict[str, str]

logger = logging.getLogger(__name__)

# --- Provider Specific Functions ---

def call_gemini(prompt: str, llm_config: LlmConfigDict) -> str:
    """Handle API call to Google Gemini."""
    if not GOOGLE_GENAI_AVAILABLE:
        raise ImportError("Google Generative AI SDK not installed.")
    if genai is None or HarmCategory is None or HarmBlockThreshold is None:
         raise RuntimeError("Google GenAI SDK components failed import.")

    api_key = llm_config.get("api_key")
    model_name = llm_config.get("model")
    if not api_key:
        raise ValueError("Missing 'api_key' for Gemini provider.")
    if not model_name:
        raise ValueError("Missing 'model' for Gemini provider.")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        # E701 fix: Separated raise
        raise LlmApiError(f"Failed configure/init Gemini model: {e}", provider="gemini") from e

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }

    try:
        response = model.generate_content(prompt, safety_settings=safety_settings)
        if (response.candidates and
            response.candidates[0].content and
            response.candidates[0].content.parts):
            return "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
        # Handle blocked/empty response
        block_reason = getattr(response.prompt_feedback, 'block_reason', 'Unknown') if response.prompt_feedback else 'N/A'
        finish_reason = getattr(response.candidates[0], 'finish_reason', 'Unknown') if response.candidates else 'N/A'
        reason = finish_reason if finish_reason != 'Unknown' else block_reason
        raise LlmApiError(f"Gemini response empty/blocked. Reason: {reason}", provider="gemini")
    except Exception as e:
        raise LlmApiError(f"Gemini API call failed: {e}", provider="gemini") from e

def call_perplexity(prompt: str, llm_config: LlmConfigDict) -> str:
    """Handle API call to Perplexity AI."""
    if not REQUESTS_AVAILABLE:
        raise ImportError("The 'requests' library is not installed.")
    if requests is None:
        raise RuntimeError("Requests library failed to import correctly.")

    api_key = llm_config.get("api_key")
    model_name = llm_config.get("model")
    if not api_key:
        raise ValueError("Missing 'api_key' for Perplexity provider.")
    if not model_name:
        raise ValueError("Missing 'model' for Perplexity provider.")

    headers: HeadersDict = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response_data = response.json()

        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
             error_msg = "Invalid/empty 'choices' in Perplexity response."
             raise LlmApiError(error_msg, response.status_code, "perplexity")

        message = choices[0].get("message")
        if not isinstance(message, dict) or "content" not in message:
             # E501 fix: Wrapped error message
             error_msg = "Invalid/missing 'message' in Perplexity choice."
             raise LlmApiError(error_msg, response.status_code, "perplexity")

        response_text = message["content"]
        if not isinstance(response_text, str):
             error_msg = "Invalid content type from Perplexity."
             raise LlmApiError(error_msg, response.status_code, "perplexity")

        return response_text
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else None
        error_detail = str(e)
        if e.response is not None:
             try:
                 error_detail = e.response.json().get('error', {}).get('message', e.response.text)
             except json.JSONDecodeError:
                 error_detail = e.response.text
        raise LlmApiError(f"API request failed: {error_detail}", status_code, "perplexity") from e
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e_parse:
         raise LlmApiError(f"Failed to parse Perplexity response: {e_parse}", provider="perplexity") from e_parse

# Add functions for other cloud providers here...

# End of src/sourcelens/utils/_cloud_llm_api.py
