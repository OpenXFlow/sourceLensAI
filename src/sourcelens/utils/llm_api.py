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

"""Main entry point for LLM API interactions.

Provides caching and dispatches calls to the appropriate provider-specific module
(_cloud_llm_api.py or _local_llm_api.py).
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Final, Optional, Protocol

from typing_extensions import TypeAlias

from . import _cloud_llm_api, _local_llm_api
from ._exceptions import LlmApiError

LlmConfigDict: TypeAlias = dict[str, Any]
CacheConfigDict: TypeAlias = dict[str, Any]

logger: logging.Logger = logging.getLogger(__name__)

LOG_PROMPT_SNIPPET_LEN: Final[int] = 100
LOG_RESPONSE_SNIPPET_LEN: Final[int] = 200


class CacheProtocol(Protocol):
    """Define the interface for a cache object."""

    def get(self, prompt: str) -> Optional[str]:
        """Retrieve an item from the cache.

        Args:
            prompt: The prompt string (used as a key).

        Returns:
            The cached response string, or None if not found.
        """
        ...  # pragma: no cover

    def put(self, prompt: str, response: str) -> None:
        """Store an item in the cache.

        Args:
            prompt: The prompt string (used as a key).
            response: The LLM response string to cache.
        """
        ...  # pragma: no cover


class LlmCache(CacheProtocol):
    """A simple file-based JSON cache for LLM prompts and responses."""

    def __init__(self, cache_file_path: Path) -> None:
        """Initialize LlmCache.

        Args:
            cache_file_path: Path to the JSON file used for caching.
        """
        self.cache_file_path: Path = cache_file_path
        self.cache: dict[str, str] = {}
        self._ensure_cache_dir()
        self.cache = self._load_cache()

    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists."""
        cache_dir: Path = self.cache_file_path.parent
        if not cache_dir.exists():
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                logger.debug("Cache directory created: %s", cache_dir)
            except OSError as e:
                logger.error("Failed to create cache directory '%s': %s.", cache_dir, e)

    def _load_cache(self) -> dict[str, str]:
        """Load cache from the JSON file.

        Returns:
            A dictionary representing the loaded cache. Returns an empty
            dictionary if the file doesn't exist or an error occurs.
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
                str_cache: dict[str, str] = {
                    str(k): str(v) for k, v in loaded_data.items() if isinstance(k, str) and isinstance(v, str)
                }
                if len(str_cache) != len(loaded_data):
                    logger.warning("Some non-string key/values removed from cache during load.")
                return str_cache
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failed to load/parse cache from %s: %s. Starting with an empty cache.", self.cache_file_path, e
            )
            return {}

    def _save_cache(self) -> None:
        """Save the current cache to the JSON file."""
        try:
            self._ensure_cache_dir()
            with self.cache_file_path.open("w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            logger.debug("LLM cache saved to %s.", self.cache_file_path)
        except (OSError, TypeError) as e:
            logger.error("Failed to save LLM cache to %s: %s", self.cache_file_path, e, exc_info=False)
        except Exception as e:
            logger.error("Unexpected error saving LLM cache: %s", e, exc_info=True)

    def get(self, prompt: str) -> Optional[str]:
        """Retrieve an item from the cache.

        Args:
            prompt: The prompt string (used as a key).

        Returns:
            The cached response string, or None if not found.
        """
        return self.cache.get(prompt)

    def put(self, prompt: str, response: str) -> None:
        """Store an item in the cache.

        Args:
            prompt: The prompt string (used as a key).
            response: The LLM response string to cache.
        """
        if not isinstance(prompt, str) or not isinstance(response, str):
            logger.warning("Attempted to cache non-string prompt or response. Skipping.")
            return
        self.cache[prompt] = response
        self._save_cache()


class DummyCache(CacheProtocol):
    """A no-op cache implementation that doesn't store anything."""

    def get(self, prompt: str) -> None:  # type: ignore[override]
        """Simulate getting from cache, always returns None.

        Args:
            prompt: The prompt string.

        Returns:
            None.
        """
        del prompt
        return None

    def put(self, prompt: str, response: str) -> None:
        """Simulate putting into cache, does nothing.

        Args:
            prompt: The prompt string.
            response: The response string.
        """
        del prompt, response


# Function to manage the cache singleton instance
def get_cache_manager() -> Callable[[CacheConfigDict], CacheProtocol]:
    """Return a function that manages a singleton cache instance.

    This approach avoids using a global variable directly in `_get_cache`
    and allows for lazy initialization of the cache.

    Returns:
        A function that, when called with cache_config, returns the
        singleton CacheProtocol instance.
    """
    # This attribute will store the singleton instance
    # It's an attribute of the get_cache_manager function itself
    if not hasattr(get_cache_manager, "_cache_instance"):
        get_cache_manager._cache_instance = None  # type: ignore[attr-defined]

    def _get_or_create_cache(cache_config: CacheConfigDict) -> CacheProtocol:
        """Get or create the cache instance."""
        instance: Optional[CacheProtocol] = getattr(get_cache_manager, "_cache_instance", None)
        if instance is None:
            use_caching_any: Any = cache_config.get("use_cache", True)
            use_caching: bool = bool(use_caching_any)

            if not use_caching:
                instance = DummyCache()
                logger.info("LLM caching is disabled.")
            else:
                cache_file_str_any: Any = cache_config.get("llm_cache_file")
                if not cache_file_str_any or not isinstance(cache_file_str_any, str):
                    logger.warning("LLM cache file path not configured or invalid. Disabling file cache.")
                    instance = DummyCache()
                else:
                    cache_file_str: str = cache_file_str_any
                    try:
                        cache_path = Path(cache_file_str).resolve()
                        instance = LlmCache(cache_path)
                        logger.info("LLM file cache initialized at: %s", cache_path)
                    except (OSError, ValueError, TypeError) as e:
                        logger.error(
                            "Failed to initialize LlmCache at '%s': %s. Disabling file cache.", cache_file_str, e
                        )
                        instance = DummyCache()
            setattr(get_cache_manager, "_cache_instance", instance)
        return instance  # Instance is now guaranteed to be CacheProtocol

    return _get_or_create_cache


# Get the cache management function
_get_cache_singleton_provider: Callable[[CacheConfigDict], CacheProtocol] = get_cache_manager()


def _get_llm_response(prompt: str, llm_config: LlmConfigDict) -> str:
    """Make the actual API call to the specified LLM provider.

    Args:
        prompt: The prompt string.
        llm_config: LLM provider configuration.

    Returns:
        The LLM's text response.

    Raises:
        ValueError: If provider is missing or unsupported.
        LlmApiError: For API errors.
        ImportError: If provider-specific libraries are missing.
    """
    provider_any: Any = llm_config.get("provider")
    model_name_any: Any = llm_config.get("model")

    if not provider_any or not isinstance(provider_any, str):
        raise ValueError("LLM provider name is missing or invalid in configuration.")
    provider: str = provider_any
    model_name_str: str = str(model_name_any) if isinstance(model_name_any, str) else "unknown_model"

    logger.debug("LLM API CALL - Provider: %s, Model: %s", provider, model_name_str)

    response_text: str
    if provider == "gemini":
        response_text = _cloud_llm_api.call_gemini(prompt, llm_config)
    elif provider == "perplexity":
        response_text = _cloud_llm_api.call_perplexity(prompt, llm_config)
    elif provider == "openai_compatible_local":
        response_text = _local_llm_api.call_local_openai_compatible(prompt, llm_config)
    else:
        raise ValueError(f"Unsupported LLM provider configured: {provider}")

    if not response_text:
        logger.warning(
            "LLM call to provider '%s' (model '%s') returned an empty response string.", provider, model_name_str
        )
    return response_text


def call_llm(prompt: str, llm_config: LlmConfigDict, cache_config: CacheConfigDict) -> str:
    """Call the configured LLM API with caching and error handling.

    Dispatches to the appropriate provider-specific function.

    Args:
        prompt: The prompt string to send to the LLM.
        llm_config: Dictionary containing configuration for the LLM provider.
        cache_config: Dictionary containing cache configuration.

    Returns:
        The text response from the LLM.

    Raises:
        ValueError: If critical configuration is missing or provider is unsupported.
        LlmApiError: If the API call to the LLM provider fails.
        ImportError: If a required library for a provider is not installed.
    """
    cache: CacheProtocol = _get_cache_singleton_provider(cache_config)
    is_real_cache_in_use = not isinstance(cache, DummyCache)

    if is_real_cache_in_use:
        cached_response = cache.get(prompt)
        if cached_response is not None:
            prompt_snippet = prompt[:LOG_PROMPT_SNIPPET_LEN].replace("\n", " ") + (
                "..." if len(prompt) > LOG_PROMPT_SNIPPET_LEN else ""
            )
            logger.info('LLM Cache HIT for prompt starting with: "%s"', prompt_snippet)
            return cached_response
        prompt_snippet = prompt[:LOG_PROMPT_SNIPPET_LEN].replace("\n", " ") + (
            "..." if len(prompt) > LOG_PROMPT_SNIPPET_LEN else ""
        )
        logger.info('LLM Cache MISS for prompt starting with: "%s"', prompt_snippet)

    try:
        response_text = _get_llm_response(prompt, llm_config)
    except (ImportError, ValueError, NotImplementedError) as e:
        provider = str(llm_config.get("provider", "Unknown"))
        logger.error("Setup/Config error for LLM provider '%s': %s", provider, e, exc_info=True)
        raise
    except LlmApiError:
        raise
    except Exception as e_unexpected:
        provider = str(llm_config.get("provider", "Unknown"))
        logger.exception("Unexpected error during LLM API call dispatch for provider '%s'", provider)
        raise LlmApiError(f"Unexpected dispatch error: {e_unexpected!s}", provider=provider) from e_unexpected

    response_snippet = response_text[:LOG_RESPONSE_SNIPPET_LEN].replace("\n", " ") + (
        "..." if len(response_text) > LOG_RESPONSE_SNIPPET_LEN else ""
    )
    logger.debug("LLM API Response Snippet: %s", response_snippet)

    if is_real_cache_in_use:
        cache.put(prompt, response_text)

    return response_text


# End of src/sourcelens/utils/llm_api.py
