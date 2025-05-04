"""Main entry point for LLM API interactions.

Provides caching and dispatches calls to the appropriate provider-specific module
(_cloud_llm_api.py or _local_llm_api.py).
"""
# ... (ostatné importy zostávajú) ...
import json
import logging
from pathlib import Path
from typing import Any, Optional, Protocol, TypeAlias

# Import provider-specific functions from internal modules
from . import _cloud_llm_api, _local_llm_api

# <<< Import error class from the new exceptions module >>>
from ._exceptions import LlmApiError

# --- Type Aliases ---
LlmConfigDict: TypeAlias = dict[str, Any]
CacheConfigDict: TypeAlias = dict[str, Any]

logger = logging.getLogger(__name__)

# --- Error Class (REMOVED FROM HERE) ---
# class LlmApiError(Exception): ...

# --- Caching Logic (remains the same) ---
class CacheProtocol(Protocol):
    def get(self, prompt: str) -> Optional[str]: ...
    def put(self, prompt: str, response: str) -> None: ...
# ... (LlmCache, DummyCache, _get_cache remain the same) ...
class LlmCache:
    def __init__(self, cache_file_path: Path) -> None:
        self.cache_file_path = cache_file_path; self.cache: dict[str, str] = {}
        self._ensure_cache_dir(); self.cache = self._load_cache()
    def _ensure_cache_dir(self) -> None:
        cache_dir = self.cache_file_path.parent
        if not cache_dir.exists():
            try: cache_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e: logger.error("Failed create cache dir '%s': %s.", cache_dir, e)
    def _load_cache(self) -> dict[str, str]:
        if not self.cache_file_path.is_file(): return {}
        try:
            with self.cache_file_path.open(encoding='utf-8') as f:
                loaded_data: dict[str, str] = json.load(f)
                if not isinstance(loaded_data, dict): return {}
                return loaded_data
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed load/parse cache from %s: %s.", self.cache_file_path, e); return {}
    def _save_cache(self) -> None:
        try:
            self._ensure_cache_dir()
            with self.cache_file_path.open('w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except (OSError, TypeError) as e: logger.error("Failed save LLM cache: %s", e, exc_info=False)
        except Exception as e: logger.error("Unexpected error saving cache: %s", e, exc_info=True)
    def get(self, prompt: str) -> Optional[str]: return self.cache.get(prompt)
    def put(self, prompt: str, response: str) -> None:
        if not isinstance(prompt, str) or not isinstance(response, str): return
        self.cache[prompt] = response; self._save_cache()

class DummyCache:
    def get(self, prompt: str) -> None: return None
    def put(self, prompt: str, response: str) -> None: pass

_llm_cache_instance: Optional[CacheProtocol] = None

def _get_cache(cache_config: CacheConfigDict) -> CacheProtocol:
    global _llm_cache_instance
    if _llm_cache_instance is None:
        if not cache_config.get("use_cache", True): _llm_cache_instance = DummyCache()
        else:
            cache_file_str = cache_config.get("llm_cache_file")
            if not cache_file_str or not isinstance(cache_file_str, str): _llm_cache_instance = DummyCache()
            else:
                 try: _llm_cache_instance = LlmCache(Path(cache_file_str).resolve())
                 except Exception as e: logger.error("Failed init LlmCache: %s.", e); _llm_cache_instance = DummyCache()
    return _llm_cache_instance if _llm_cache_instance is not None else DummyCache()


# --- Main Dispatcher Function ---
def call_llm(
    prompt: str,
    llm_config: LlmConfigDict,
    cache_config: CacheConfigDict
) -> str:
    """Call the configured LLM API with caching and error handling."""
    # ... (cache check logic remains the same) ...
    provider = llm_config.get("provider")
    model_name = llm_config.get("model")
    if not provider: raise ValueError("LLM provider missing.")
    cache = _get_cache(cache_config)
    use_cache = not isinstance(cache, DummyCache)
    if use_cache:
        cached_response = cache.get(prompt)
        if cached_response is not None:
            prompt_snippet = prompt[:100].replace('\n', ' ') + ('...' if len(prompt) > 100 else '')
            logger.info("LLM Cache HIT for: %s", prompt_snippet)
            return cached_response
        prompt_snippet = prompt[:100].replace('\n', ' ') + ('...' if len(prompt) > 100 else '')
        logger.info("LLM Cache MISS for: %s", prompt_snippet)

    logger.debug("LLM API CALL - Provider: %s, Model: %s", provider, model_name)

    response_text: str = ""
    try:
        # Dispatch based on provider name
        if provider == "gemini":
            response_text = _cloud_llm_api.call_gemini(prompt, llm_config)
        elif provider == "perplexity":
            response_text = _cloud_llm_api.call_perplexity(prompt, llm_config)
        elif provider == "openai_compatible_local":
            response_text = _local_llm_api.call_local_openai_compatible(prompt, llm_config)
        # Add elif blocks for other providers here...
        # elif provider == "openai": response_text = _cloud_llm_api.call_openai(prompt, llm_config)
        # elif provider == "anthropic": response_text = _cloud_llm_api.call_anthropic(prompt, llm_config)
        # elif provider == "vertexai": response_text = _cloud_llm_api.call_vertexai(prompt, llm_config)
        else:
            raise ValueError(f"Unsupported LLM provider configured: {provider}")

    except (ImportError, ValueError, NotImplementedError) as e:
         logger.error("Setup/Config error for provider '%s': %s", provider, e)
         raise
    except LlmApiError: # LlmApiError is now imported from _exceptions
         raise
    except Exception as e:
        logger.exception("Unexpected error during LLM API call dispatch for %s", provider)
        raise LlmApiError(f"Unexpected error: {e}", provider=provider) from e # Use imported LlmApiError

    if not response_text:
         logger.warning("LLM call to %s model '%s' returned empty response.", provider, model_name)

    response_snippet = response_text[:200].replace('\n', ' ') + ('...' if len(response_text) > 200 else '')
    logger.debug("LLM API Response Snippet: %s", response_snippet)

    if use_cache: cache.put(prompt, response_text)

    return response_text

# End of src/sourcelens/utils/llm_api.py
