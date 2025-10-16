# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Node responsible for translating and reformatting a YouTube transcript.

This node takes the original transcript text (which may include time block headers),
translates it to the project's target language using an LLM, and instructs the LLM
to reformat the output. The LLM should remove time block headers, deduplicate
repetitive sentences/phrases, place each sentence on a new line, and group
sentences into paragraphs.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.utils.llm_api import LlmApiError, call_llm

if TYPE_CHECKING:  # pragma: no cover
    from sourcelens.core.common_types import CacheConfigDict, FilePathContentList, LlmConfigDict

from ..prompts import TranslationPrompts
from .n01c_youtube_content import (
    TRANSCRIPTS_SUBDIR_NAME,  # For saving file in correct subdirectory
    StandaloneTranscriptSaveData,  # For creating save_data object
)

TranslateYouTubeTranscriptPreparedInputs: TypeAlias = dict[str, Any]
TranslateYouTubeTranscriptExecutionResult: TypeAlias = Optional[str]

module_logger_yt_translate: logging.Logger = logging.getLogger(__name__)

LANGUAGE_NAME_MAP: Final[dict[str, str]] = {
    "en": "English",
    "sk": "Slovak",
    "cs": "Czech",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
}
DEFAULT_LANGUAGE_NAME: Final[str] = "the source language"
STANDALONE_TRANSCRIPT_FORMAT_TRANSLATE: Final[str] = "md"
FINAL_TRANSCRIPT_FILE_FOR_PIPELINE_PREFIX: Final[str] = "_youtube_final_transcript_for_llm"


class TranslateYouTubeTranscript(
    BaseNode[TranslateYouTubeTranscriptPreparedInputs, TranslateYouTubeTranscriptExecutionResult]
):
    """Translate and reformat a YouTube transcript using an LLM."""

    def _get_language_full_name(self, lang_code: Optional[str]) -> str:
        """Get the full name of a language from its code.

        Args:
            lang_code: The ISO 639-1 language code, or None.

        Returns:
            The full language name or a default if not found/None.
        """
        if not lang_code:
            return DEFAULT_LANGUAGE_NAME
        return LANGUAGE_NAME_MAP.get(lang_code.lower(), lang_code)

    def pre_execution(self, shared_context: SLSharedContext) -> TranslateYouTubeTranscriptPreparedInputs:
        """Prepare data for translating and reformatting the YouTube transcript.

        This node will attempt to run if a YouTube video was processed and
        an original transcript text is available, to ensure LLM-based formatting.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary with data for execution, or `{"skip": True}`.
        """
        self._log_info("Preparing for YouTube transcript translation/reformatting.")
        shared_context["current_youtube_final_transcript_path"] = None
        shared_context["current_youtube_final_transcript_lang"] = None

        if not shared_context.get("youtube_processed_successfully", False):
            return {"skip": True, "reason": "YouTube content not successfully processed by FetchYouTubeContent."}

        video_id: Optional[str] = cast(Optional[str], shared_context.get("current_youtube_video_id"))
        sanitized_title: Optional[str] = cast(Optional[str], shared_context.get("current_youtube_sanitized_title"))
        original_lang_code: Optional[str] = cast(Optional[str], shared_context.get("current_youtube_original_lang"))
        original_transcript_text: Optional[str] = cast(
            Optional[str], shared_context.get("current_youtube_original_transcript_text")
        )
        run_specific_output_dir_str: Optional[str] = cast(
            Optional[str], shared_context.get("final_output_dir_web_crawl")
        )

        if not (
            video_id
            and sanitized_title
            and original_lang_code
            and original_transcript_text
            and run_specific_output_dir_str
        ):
            return {"skip": True, "reason": "Missing critical YouTube context for translation/reformatting."}

        if not original_transcript_text.strip():  # pragma: no cover
            self._log_warning("Original transcript text for video %s is empty. Skipping.", video_id)
            return {"skip": True, "reason": "Original transcript text is empty."}

        target_language_code: str = str(shared_context.get("language", "en"))
        self._log_info(
            "Proceeding with LLM for transcript of video %s. Source: %s, Target: %s. (Will reformat if same lang)",
            video_id,
            original_lang_code,
            target_language_code,
        )

        llm_config: "LlmConfigDict" = self._get_required_shared(shared_context, "llm_config")  # type: ignore[assignment]
        cache_config: "CacheConfigDict" = self._get_required_shared(shared_context, "cache_config")  # type: ignore[assignment]

        return {
            "skip": False,
            "video_id": video_id,
            "sanitized_video_title": sanitized_title,
            "video_title_raw": cast(Optional[str], shared_context.get("current_youtube_video_title")),
            "text_to_translate": original_transcript_text,  # This now contains time blocks
            "source_language_code": original_lang_code,
            "target_language_code": target_language_code,
            "run_specific_output_dir": Path(run_specific_output_dir_str),
            "youtube_url": cast(Optional[str], shared_context.get("current_youtube_url")),
            "llm_config": llm_config,
            "cache_config": cache_config,
        }

    def execution(
        self, prepared_inputs: TranslateYouTubeTranscriptPreparedInputs
    ) -> TranslateYouTubeTranscriptExecutionResult:
        """Translate and reformat the transcript content using an LLM.

        Args:
            prepared_inputs: Data from `pre_execution`.

        Returns:
            The translated and reformatted text string, or None if failed or skipped.
        """
        if prepared_inputs.get("skip", True):
            reason: str = str(prepared_inputs.get("reason", "N/A"))
            self._log_info("Skipping transcript translation/reformatting. Reason: %s", reason)
            return None

        text_to_translate: str = prepared_inputs["text_to_translate"]  # This text includes time blocks
        source_lang_code: str = prepared_inputs["source_language_code"]
        target_lang_code: str = prepared_inputs["target_language_code"]
        llm_config: "LlmConfigDict" = prepared_inputs["llm_config"]  # type: ignore[assignment]
        cache_config: "CacheConfigDict" = prepared_inputs["cache_config"]  # type: ignore[assignment]

        source_lang_name = self._get_language_full_name(source_lang_code)
        target_lang_name = self._get_language_full_name(target_lang_code)

        log_action = (
            "Reformatting"
            if source_lang_code.lower() == target_lang_code.lower()
            else f"Translating from {source_lang_name} ({source_lang_code}) to {target_lang_name} ({target_lang_code})"
        )
        self._log_info("%s transcript for video ID '%s'...", log_action, prepared_inputs["video_id"])

        prompt = TranslationPrompts.format_translate_text_prompt(
            text_to_translate=text_to_translate,
            source_language_name=source_lang_name,
            target_language_name=target_lang_name,
        )
        if not prompt:  # pragma: no cover
            self._log_warning("Translation prompt is empty (text_to_translate was empty). Skipping LLM call.")
            return None

        try:
            translated_text: str = call_llm(prompt, llm_config, cache_config)
            if not translated_text.strip():  # pragma: no cover
                self._log_warning("LLM returned empty translation/reformatted text. Treating as failure.")
                return None
            # The LLM output should now be without time blocks and correctly formatted
            return translated_text.strip()
        except LlmApiError:  # pragma: no cover
            self._log_error("LLM call failed during transcript translation/reformatting.", exc_info=True)
            raise
        except Exception as e_unexpected:  # pragma: no cover # pylint: disable=broad-except
            self._log_error("Unexpected error during LLM call: %s", e_unexpected, exc_info=True)
            raise LlmApiError(f"Unexpected translation error: {e_unexpected!s}") from e_unexpected

    def execution_fallback(
        self, prepared_inputs: TranslateYouTubeTranscriptPreparedInputs, exc: Exception
    ) -> TranslateYouTubeTranscriptExecutionResult:
        """Handle fallback if all translation/reformatting attempts fail.

        Args:
            prepared_inputs: Data from `pre_execution`.
            exc: The exception from the last execution attempt.

        Returns:
            Always None for this node, as failure means no usable content.
        """
        video_id_fallback: str = str(prepared_inputs.get("video_id", "Unknown Video"))
        self._log_error(
            "All attempts to translate/reformat transcript for video ID '%s' failed. Last error: %s",
            video_id_fallback,
            exc,
            exc_info=True,
        )
        return None

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: TranslateYouTubeTranscriptPreparedInputs,
        execution_outputs: TranslateYouTubeTranscriptExecutionResult,
    ) -> None:
        """Save the final (translated/reformatted) transcript and update shared_context.

        Args:
            shared_context: The shared context dictionary.
            prepared_inputs: Data from `pre_execution`.
            execution_outputs: The translated/reformatted text, or None.
        """
        if prepared_inputs.get("skip", True) or not execution_outputs:
            if not prepared_inputs.get("skip", True):
                self._log_warning("Translation/reformatting failed, no final transcript to save.")
            shared_context.setdefault("current_youtube_final_transcript_path", None)
            shared_context.setdefault("current_youtube_final_transcript_lang", None)
            return

        sanitized_title: str = prepared_inputs["sanitized_video_title"]
        target_lang_code: str = prepared_inputs["target_language_code"]
        run_specific_output_dir: Path = prepared_inputs["run_specific_output_dir"]
        video_title: str = prepared_inputs.get("video_title_raw") or prepared_inputs["video_id"]
        youtube_url: Optional[str] = prepared_inputs.get("youtube_url")
        video_id: str = prepared_inputs["video_id"]

        transcripts_dir = run_specific_output_dir / TRANSCRIPTS_SUBDIR_NAME
        try:
            transcripts_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:  # pragma: no cover
            self._log_error("Failed to create transcripts directory %s: %s", transcripts_dir, e)
            return

        save_data = StandaloneTranscriptSaveData(
            transcripts_output_dir=transcripts_dir,
            video_id=video_id,
            sanitized_video_title=sanitized_title,
            video_title=video_title,
            original_lang=target_lang_code,
            original_text=execution_outputs,
            youtube_url=youtube_url,
            output_format=STANDALONE_TRANSCRIPT_FORMAT_TRANSLATE,
            is_translated=True,
        )
        try:
            from .n01c_youtube_content import FetchYouTubeContent as FYTC

            fytc_instance_for_saving = FYTC()
            final_saved_path = fytc_instance_for_saving._save_standalone_transcript_file_yt(save_data)
        except ImportError:  # pragma: no cover
            self._log_error("Could not import FetchYouTubeContent for saving transcript. Save failed.")
            final_saved_path = None

        if final_saved_path:
            shared_context["current_youtube_final_transcript_path"] = final_saved_path
            shared_context["current_youtube_final_transcript_lang"] = target_lang_code
            self._log_info("Final transcript saved and context updated: %s", final_saved_path)

            config: dict[str, Any] = cast(dict, shared_context.get("config", {}))
            crawler_opts: dict[str, Any] = config.get("FL02_web_crawling", {}).get("crawler_options", {})
            proc_mode: str = str(crawler_opts.get("processing_mode", "minimalistic"))

            if proc_mode == "llm_extended":
                final_transcript_filename_key = f"{FINAL_TRANSCRIPT_FILE_FOR_PIPELINE_PREFIX}_{target_lang_code}.md"
                files_list: "FilePathContentList" = cast(list, shared_context.get("files", []))
                files_list.append((final_transcript_filename_key, execution_outputs))
                shared_context["files"] = files_list
                self._log_info("Added final formatted transcript to shared_context['files'] for LLM pipeline.")
        else:  # pragma: no cover
            self._log_error("Failed to save the final (translated/reformatted) transcript.")


# End of src/FL02_web_crawling/nodes/n07b_translate_youtube_transcript.py
