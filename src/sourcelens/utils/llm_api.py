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

"""Main entry point for LLM API interactions.

Provides caching and dispatches calls to the appropriate provider-specific module
(_cloud_llm_api.py or _local_llm_api.py).
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Final, Optional, Protocol

from sourcelens.core.common_types import CacheConfigDict, LlmConfigDict

from . import _cloud_llm_api, _local_llm_api
from ._exceptions import LlmApiError

logger: logging.Logger = logging.getLogger(__name__)

LOG_PROMPT_SNIPPET_LEN: Final[int] = 100
LOG_RESPONSE_SNIPPET_LEN: Final[int] = 200


class CacheProtocol(Protocol):
    """Define the interface for a cache object.

    This protocol outlines the methods that any cache implementation used by
    the LLM API module must provide.
    """

    def get(self, prompt: str) -> Optional[str]:
        """Retrieve an item from the cache based on the prompt.

        Args:
            prompt: The prompt string used as the cache key.

        Returns:
            The cached response string if found, otherwise None.
        """
        ...  # pragma: no cover

    def put(self, prompt: str, response: str) -> None:
        """Store an item (prompt-response pair) in the cache.

        Args:
            prompt: The prompt string to use as the cache key.
            response: The LLM response string to store.
        """
        ...  # pragma: no cover


class LlmCache(CacheProtocol):
    """Implement a simple file-based JSON cache for LLM prompts and responses.

    This class provides a persistent cache mechanism, storing prompt-response
    pairs in a JSON file to avoid redundant LLM API calls for identical prompts.
    """

    cache_file_path: Path
    cache: dict[str, str]

    def __init__(self, cache_file_path: Path) -> None:
        """Initialize LlmCache and load existing cache from file.

        Args:
            cache_file_path: The `Path` object pointing to the JSON cache file.
                             The directory for this file will be created if it
                             doesn't exist.
        """
        self.cache_file_path = cache_file_path
        self.cache = {}
        self._ensure_cache_dir()
        self.cache = self._load_cache()
        logger.debug("LlmCache initialized with file: %s", self.cache_file_path)

    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists, creating it if necessary."""
        cache_dir: Path = self.cache_file_path.parent
        if not cache_dir.exists():
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                logger.debug("Cache directory created: %s", cache_dir)
            except OSError as e:
                logger.error("Failed to create cache directory '%s': %s.", cache_dir, e)

    def _load_cache(self) -> dict[str, str]:
        """Load the cache from the JSON file.

        If the cache file does not exist or is invalid, an empty cache is returned.

        Returns:
            A dictionary representing the loaded cache.
        """
        if not self.cache_file_path.is_file():
            logger.debug("Cache file not found at %s. Starting with an empty cache.", self.cache_file_path)
            return {}
        try:
            with self.cache_file_path.open(encoding="utf-8") as f:
                loaded_data: Any = json.load(f)
                if not isinstance(loaded_data, dict):
                    logger.warning("Cache data in %s is not a dictionary. Resetting cache.", self.cache_file_path)
                    return {}
                # Ensure keys and values are strings
                str_cache: dict[str, str] = {
                    str(k): str(v) for k, v in loaded_data.items() if isinstance(k, str) and isinstance(v, str)
                }
                if len(str_cache) != len(loaded_data):  # pragma: no cover
                    logger.warning("Some non-string key/values removed from cache during load.")
                logger.debug("Loaded %d items from cache file: %s", len(str_cache), self.cache_file_path)
                return str_cache
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failed to load/parse cache from %s: %s. Starting with an empty cache.", self.cache_file_path, e
            )
            return {}

    def _save_cache(self) -> None:
        """Save the current state of the cache to the JSON file."""
        try:
            self._ensure_cache_dir()  # Ensure directory exists before writing
            with self.cache_file_path.open("w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            logger.debug("LLM cache saved to %s. Cache size: %d items.", self.cache_file_path, len(self.cache))
        except (OSError, TypeError) as e:  # pragma: no cover
            logger.error("Failed to save LLM cache to %s: %s", self.cache_file_path, e, exc_info=False)
        except Exception as e:  # pragma: no cover
            logger.error("Unexpected error saving LLM cache: %s", e, exc_info=True)

    def get(self, prompt: str) -> Optional[str]:
        """Retrieve an item from the cache based on the prompt.

        Args:
            prompt: The prompt string used as the cache key.

        Returns:
            The cached response string if found, otherwise None.
        """
        return self.cache.get(prompt)

    def put(self, prompt: str, response: str) -> None:
        """Store an item (prompt-response pair) in the cache and save it.

        Args:
            prompt: The prompt string to use as the cache key.
            response: The LLM response string to store.
        """
        if not isinstance(prompt, str) or not isinstance(response, str):
            logger.warning("Attempted to cache non-string prompt or response. Skipping.")
            return
        self.cache[prompt] = response
        self._save_cache()


class DummyCache(CacheProtocol):
    """Implement a no-op cache that does not store any data.

    This class can be used when caching is disabled, providing the same
    interface as `LlmCache` but without performing any caching operations.
    """

    def get(self, prompt: str) -> Optional[str]:  # Changed return type to Optional[str]
        """Simulate getting from cache, always returns None.

        Args:
            prompt: The prompt string (unused).

        Returns:
            Always None, as this cache does not store items.
        """
        del prompt  # Mark as unused
        return None

    def put(self, prompt: str, response: str) -> None:
        """Simulate putting into cache, performs no action.

        Args:
            prompt: The prompt string (unused).
            response: The LLM response string (unused).
        """
        del prompt, response  # Mark as unused


def get_cache_manager() -> Callable[[CacheConfigDict], CacheProtocol]:
    """Return a factory function that manages a singleton cache instance.

    This function uses a closure to maintain a single instance of the cache
    throughout the application's lifecycle, creating it on first call based
    on the provided `cache_config`.

    Returns:
        A callable that, when invoked with `CacheConfigDict`, returns the
        singleton `CacheProtocol` instance (either `LlmCache` or `DummyCache`).
    """
    if not hasattr(get_cache_manager, "_cache_instance"):
        # Initialize attribute to store the singleton cache instance
        setattr(get_cache_manager, "_cache_instance", None)

    def _get_or_create_cache(cache_config: CacheConfigDict) -> CacheProtocol:
        """Get or create the singleton cache instance based on configuration.

        If caching is enabled in `cache_config` and a valid file path is provided,
        an `LlmCache` instance is created. Otherwise, a `DummyCache` is used.

        Args:
            cache_config: Configuration dictionary for caching. Expected keys:
                          'use_llm_cache' (bool), 'llm_cache_file' (str).

        Returns:
            The initialized cache instance (either `LlmCache` or `DummyCache`).
        """
        instance: Optional[CacheProtocol] = getattr(get_cache_manager, "_cache_instance", None)
        if instance is None:
            use_caching_any: Any = cache_config.get("use_llm_cache", True)
            use_caching: bool = bool(use_caching_any)

            if not use_caching:
                instance = DummyCache()
                logger.info("LLM caching is disabled by configuration.")
            else:
                cache_file_str_any: Any = cache_config.get("llm_cache_file")
                if not cache_file_str_any or not isinstance(cache_file_str_any, str):
                    logger.warning("LLM cache file path not configured or invalid. Disabling file-based cache.")
                    instance = DummyCache()
                else:
                    cache_file_str: str = cache_file_str_any
                    try:
                        cache_path = Path(cache_file_str).resolve()
                        instance = LlmCache(cache_path)
                        logger.info("LLM file cache initialized at: %s", cache_path)
                    except (OSError, ValueError, TypeError) as e:  # pragma: no cover
                        logger.error(
                            "Failed to initialize LlmCache at '%s': %s. Disabling file-based cache.", cache_file_str, e
                        )
                        instance = DummyCache()
            setattr(get_cache_manager, "_cache_instance", instance)
        return instance

    return _get_or_create_cache


_get_cache_singleton_provider: Callable[[CacheConfigDict], CacheProtocol] = get_cache_manager()


def _get_llm_response(prompt: str, llm_config: LlmConfigDict) -> str:
    """Dispatch the LLM API call to the appropriate provider-specific function.

    This internal helper function selects the correct API calling function
    (e.g., `call_gemini`, `call_local_openai_compatible`) based on the 'provider'
    field in `llm_config`.

    Args:
        prompt: The prompt string to send to the LLM.
        llm_config: Configuration dictionary for the LLM provider, containing
                    at least 'provider' and 'model'.

    Returns:
        The text response from the LLM.

    Raises:
        ValueError: If the 'provider' is missing, invalid, or unsupported.
        LlmApiError: Propagated from the provider-specific call functions if an
                     API error occurs.
    """
    logger.debug(
        "Dispatching LLM call. Config (API key redacted): %s",
        json.dumps({k: (v if k != "api_key" else "***REDACTED***") for k, v in llm_config.items()}, indent=2),
    )

    provider_any: Any = llm_config.get("provider")
    model_name_any: Any = llm_config.get("model")

    if not provider_any or not isinstance(provider_any, str):
        raise ValueError("LLM provider name is missing or invalid in configuration.")
    provider: str = provider_any.lower()  # Normalize provider name
    model_name_str: str = str(model_name_any) if isinstance(model_name_any, str) else "unknown_model"

    logger.debug("LLM API Call - Provider: %s, Model: %s", provider, model_name_str)

    response_text: str
    if provider == "gemini":
        response_text = _cloud_llm_api.call_gemini(prompt, llm_config)
    elif provider == "perplexity":
        response_text = _cloud_llm_api.call_perplexity(prompt, llm_config)
    elif provider in ("openai_compatible_local", "openai_compatible"):  # Handle both specific and general
        if provider == "openai_compatible":  # pragma: no cover
            logger.warning("Provider 'openai_compatible' used; assuming local. Calling call_local_openai_compatible.")
        response_text = _local_llm_api.call_local_openai_compatible(prompt, llm_config)
    # Add other providers here:
    # elif provider == "anthropic":
    #     response_text = _cloud_llm_api.call_anthropic(prompt, llm_config)
    # elif provider == "openai": # For official OpenAI API
    #     response_text = _cloud_llm_api.call_openai(prompt, llm_config)
    else:
        raise ValueError(f"Unsupported LLM provider configured: {provider}")

    if not response_text:  # pragma: no cover
        logger.warning(
            "LLM call to provider '%s' (model '%s') returned an empty response string.", provider, model_name_str
        )
    return response_text


def call_llm(prompt: str, llm_config: LlmConfigDict, cache_config: CacheConfigDict) -> str:
    """Call the configured LLM API with caching and error handling.

    This is the main public function for interacting with LLMs. It first checks
    the cache for a response to the given prompt. If not found (cache miss),
    it calls the appropriate LLM provider via `_get_llm_response`. The new
    response is then stored in the cache if caching is enabled.

    Args:
        prompt: The prompt string to send to the LLM.
        llm_config: Configuration dictionary for the LLM API, including provider,
                    model, API key, etc.
        cache_config: Configuration dictionary for LLM response caching, including
                      whether to use cache and the cache file path.

    Returns:
        The text response from the LLM.

    Raises:
        ValueError: If LLM provider configuration in `llm_config` is invalid
                    or an unsupported provider is specified.
        ImportError: If a required library for a specific LLM provider is not installed
                     (raised from provider-specific functions).
        LlmApiError: For errors during the API call itself (e.g., network issues,
                     API errors, authentication failures) or if the LLM response
                     is problematic (e.g., empty, blocked).
        Exception: For any other unexpected errors during the process.
    """
    logger.debug(
        "call_llm entry: llm_config (API key redacted): %s",
        json.dumps({k: (v if k != "api_key" else "***REDACTED***") for k, v in llm_config.items()}, indent=2),
    )
    logger.debug("call_llm entry: cache_config: %s", json.dumps(cache_config, indent=2))

    cache: CacheProtocol = _get_cache_singleton_provider(cache_config)
    is_real_cache_in_use: bool = not isinstance(cache, DummyCache)

    if is_real_cache_in_use:
        cached_response: Optional[str] = cache.get(prompt)
        if cached_response is not None:
            prompt_snippet: str = prompt[:LOG_PROMPT_SNIPPET_LEN].replace("\n", " ") + (
                "..." if len(prompt) > LOG_PROMPT_SNIPPET_LEN else ""
            )
            logger.info('LLM Cache HIT for prompt starting with: "%s"', prompt_snippet)
            return cached_response
        prompt_snippet_miss: str = prompt[:LOG_PROMPT_SNIPPET_LEN].replace("\n", " ") + (
            "..." if len(prompt) > LOG_PROMPT_SNIPPET_LEN else ""
        )
        logger.info('LLM Cache MISS for prompt starting with: "%s"', prompt_snippet_miss)

    try:
        response_text: str = _get_llm_response(prompt, llm_config)
    except (ImportError, ValueError, NotImplementedError) as e:  # These are setup/config errors
        provider_name: str = str(llm_config.get("provider", "Unknown"))
        logger.error("Setup/Config error for LLM provider '%s': %s", provider_name, e, exc_info=True)
        raise  # Re-raise to be handled by the caller or flow engine
    except LlmApiError:  # API errors from provider-specific calls
        raise  # Re-raise to be handled by the caller or flow engine
    except Exception as e_unexpected:  # pragma: no cover
        # Catch any other unexpected errors during the dispatch or call
        provider_name_unexp: str = str(llm_config.get("provider", "Unknown"))
        logger.exception("Unexpected error during LLM API call dispatch for provider '%s'", provider_name_unexp)
        raise LlmApiError(
            f"Unexpected dispatch error: {e_unexpected!s}", provider=provider_name_unexp
        ) from e_unexpected

    response_snippet: str = response_text[:LOG_RESPONSE_SNIPPET_LEN].replace("\n", " ") + (
        "..." if len(response_text) > LOG_RESPONSE_SNIPPET_LEN else ""
    )
    logger.debug("LLM API Response Snippet: %s", response_snippet)

    if is_real_cache_in_use:
        cache.put(prompt, response_text)

    return response_text


# End of src/sourcelens/utils/llm_api.py
