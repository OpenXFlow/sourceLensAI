# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Node responsible for fetching and processing content from YouTube videos using yt-dlp.

This node leverages the yt-dlp library to extract video metadata (title, ID,
description, upload date, view count) and to download video transcripts
(subtitles). It prioritizes manual transcripts over automatically generated ones (ASR)
and supports a list of preferred languages.
The extracted original transcript undergoes an LLM-based deduplication step
(while preserving time blocks) before being saved and passed on.
The plain text transcript and description are made available for further processing.
An optional, hidden CLI flag (--extract-audio) can enable MP3 audio download.
"""

import io
import json
import logging
import re
import subprocess  # nosec B404: Use of subprocess is for a controlled internal tool (yt-dlp).
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional, Union, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.core.common_types import CacheConfigDict, LlmConfigDict
from sourcelens.utils.helpers import (
    sanitize_filename,
)
from sourcelens.utils.llm_api import LlmApiError, call_llm

from ..prompts.deduplication_prompts import OriginalTranscriptDeduplicationPrompts

YTDLP_AVAILABLE: bool = False
WEBVTT_AVAILABLE: bool = False
yt_dlp_module: Optional[Any] = None
webvtt_module: Optional[Any] = None
WebVTT_errors_module: Optional[Any] = None

YtdlpDownloadError: type[Exception] = Exception
YtdlpExtractorError: type[Exception] = Exception
YtdlpUnavailableVideoError: type[Exception] = Exception

module_logger_yt_content_ytdlp: logging.Logger = logging.getLogger(__name__)

try:
    import yt_dlp as imported_yt_dlp_module

    yt_dlp_module = imported_yt_dlp_module
    if hasattr(yt_dlp_module, "utils"):
        YtdlpDownloadError = getattr(yt_dlp_module.utils, "DownloadError", Exception)
        YtdlpExtractorError = getattr(yt_dlp_module.utils, "ExtractorError", Exception)
        YtdlpUnavailableVideoError = getattr(yt_dlp_module.utils, "UnavailableVideoError", Exception)
    YTDLP_AVAILABLE = True
    module_logger_yt_content_ytdlp.debug("yt-dlp library successfully imported.")
except ImportError:  # pragma: no cover
    module_logger_yt_content_ytdlp.warning("yt-dlp library not found. YouTube processing may be limited.")

try:
    import webvtt as imported_webvtt_library

    webvtt_module = imported_webvtt_library
    if hasattr(webvtt_module, "errors"):
        WebVTT_errors_module = webvtt_module.errors  # type: ignore[attr-defined]
    WEBVTT_AVAILABLE = True
    module_logger_yt_content_ytdlp.debug("webvtt-py library successfully imported.")
except ImportError:  # pragma: no cover
    module_logger_yt_content_ytdlp.warning("webvtt-py library not found. VTT parsing will rely on regex fallback.")


if TYPE_CHECKING:  # pragma: no cover
    from sourcelens.core.common_types import FilePathContentList

    if WEBVTT_AVAILABLE and webvtt_module is not None:
        from webvtt import WebVTT as ImportedWebVTT  # type: ignore[import-untyped]


FetchYouTubeContentPreparedInputsYtdlp: TypeAlias = dict[str, Any]
FetchYouTubeContentExecutionResultYtdlp: TypeAlias = Optional[dict[str, Any]]
YdlInfoDict: TypeAlias = dict[str, Any]
YdlOpts: TypeAlias = dict[str, Any]

YOUTUBE_URL_PATTERNS_NODE_YTDLP: Final[list[re.Pattern[str]]] = [
    re.compile(r"(?:v=|\/|embed\/|watch\?v=|youtu\.be\/)([0-9A-Za-z_-]{11}).*"),
    re.compile(r"shorts\/([0-9A-Za-z_-]{11})"),
]
TRANSCRIPTS_SUBDIR_NAME: Final[str] = "transcripts"
AUDIO_SUBDIR_NAME: Final[str] = "audio"
HARDCODED_SAVE_STANDALONE_TRANSCRIPT: Final[bool] = True
HARDCODED_STANDALONE_TRANSCRIPT_FORMAT: Final[str] = "md"
HARDCODED_PREFER_MANUAL_OVER_AUTO: Final[bool] = True
HARDCODED_FALLBACK_TO_AUTO_CAPTIONS: Final[bool] = True
HARDCODED_PREFERRED_SUBTITLE_DOWNLOAD_FORMAT: Final[str] = "vtt"
CLI_DOWNLOAD_TIMEOUT_SECONDS: Final[int] = 60
DESCRIPTION_FILE_FOR_PIPELINE: Final[str] = "_youtube_video_description.md"
_DOWNLOAD_AUDIO_MP3_SECRET_FEATURE_ENABLED: Final[bool] = False
EXPECTED_VTT_TIME_PARTS: Final[int] = 3
EXPECTED_VTT_SEC_MILLISECOND_PARTS: Final[int] = 2


class SubtitleType(str, Enum):
    """Define types of subtitles available or requested from YouTube.

    Enum Members:
        MANUAL: Subtitles created manually by a human.
        AUTOMATIC: Subtitles generated automatically by speech-to-text (ASR).
        NONE: Represents a state where no suitable subtitle type was chosen or found.
    """

    MANUAL = "manual"
    AUTOMATIC = "automatic"
    NONE = "none"


@dataclass
class YouTubeContextUpdateInfo:
    """Hold information for updating shared_context regarding YouTube processing.

    Attributes:
        processed_successfully: Flag indicating if processing was successful.
        video_id: The ID of the YouTube video.
        original_lang: The language code of the original transcript.
        standalone_transcript_path: Path to the saved standalone original transcript.
        video_title: The title of the YouTube video.
        run_specific_output_dir: The output directory for this specific run.
        youtube_url: The original YouTube URL.
        video_description: The description of the video.
        upload_date: The upload date of the video.
        view_count: The number of views for the video.
        uploader: The uploader of the video.
        original_transcript_text: The text of the original transcript.
        downloaded_audio_path: Path to the downloaded audio file, if any.
    """

    processed_successfully: bool
    video_id: Optional[str]
    original_lang: Optional[str]
    standalone_transcript_path: Optional[str]
    video_title: Optional[str]
    run_specific_output_dir: Optional[Path]
    youtube_url: Optional[str] = None
    video_description: Optional[str] = None
    upload_date: Optional[str] = None
    view_count: Optional[int] = None
    uploader: Optional[str] = None
    original_transcript_text: Optional[str] = None
    downloaded_audio_path: Optional[str] = None


@dataclass
class VideoMetadata:
    """Hold essential video metadata extracted from YouTube.

    Attributes:
        id: The unique ID of the video.
        title: The title of the video.
        description: The description of the video.
        upload_date: The upload date of the video (YYYYMMDD).
        view_count: The number of views.
        uploader: The name of the video uploader.
        available_manual_langs: List of lang codes for available manual subtitles.
        available_auto_langs: List of lang codes for available automatic subtitles.
        raw_subtitles_info: Raw dict of manual subtitle info from yt-dlp.
        raw_auto_captions_info: Raw dict of automatic caption info from yt-dlp.
    """

    id: str
    title: str
    description: Optional[str]
    upload_date: Optional[str]
    view_count: Optional[int]
    uploader: Optional[str]
    available_manual_langs: list[str]
    available_auto_langs: list[str]
    raw_subtitles_info: dict[str, Any]
    raw_auto_captions_info: dict[str, Any]


@dataclass
class SubtitleAttemptTarget:
    """Represent a specific subtitle (language and type) to attempt to download.

    Attributes:
        lang_code: The ISO language code of the subtitle (e.g., "en", "sk").
        type: The type of the subtitle (manual or automatic).
    """

    lang_code: str
    type: SubtitleType


@dataclass
class DownloadedSubtitleInfo:
    """Hold information about a successfully downloaded and parsed subtitle.

    Attributes:
        text: The parsed text content of the subtitle.
        lang_code: The language code of the downloaded subtitle.
        type: The type (manual/automatic) of the downloaded subtitle.
    """

    text: str
    lang_code: str
    type: SubtitleType


@dataclass
class StandaloneTranscriptSaveData:
    """Data required for saving a standalone transcript file.

    Attributes:
        transcripts_output_dir: Directory to save the transcript file.
        video_id: ID of the video. Must be a string.
        sanitized_video_title: Sanitized title of the video for filename.
        video_title: Original title of the video for header. Must be a string.
        original_lang: Language code of the transcript. Must be a string.
        original_text: The text content of the transcript.
        youtube_url: Original URL of the YouTube video.
        output_format: Format of the output file (e.g., "md", "txt").
        is_translated: Flag indicating if this transcript is a translated version.
    """

    transcripts_output_dir: Path
    video_id: str
    sanitized_video_title: str
    video_title: str
    original_lang: str
    original_text: str
    youtube_url: Optional[str]
    output_format: str
    is_translated: bool


@dataclass
class LibraryDownloadParams:
    """Parameters for downloading subtitles via yt-dlp library.

    Attributes:
        youtube_url: The URL of the YouTube video.
        actual_video_id: The confirmed video ID.
        preferred_format: The preferred subtitle format (e.g., "vtt").
        temp_dir_path: Path to the temporary directory for downloads.
    """

    youtube_url: str
    actual_video_id: str
    preferred_format: str
    temp_dir_path: Path


@dataclass
class CliDownloadParams:
    """Parameters for downloading subtitles via yt-dlp CLI.

    Attributes:
        youtube_url: The URL of the YouTube video.
        actual_video_id: The confirmed video ID.
        preferred_format: The preferred subtitle format (e.g., "vtt").
        temp_dir_path: Path to the temporary directory for downloads.
    """

    youtube_url: str
    actual_video_id: str
    preferred_format: str
    temp_dir_path: Path


@dataclass
class VideoAndFormatInfo:
    """Combined video and preferred format information for subtitle download.

    Attributes:
        youtube_url: The URL of the YouTube video.
        actual_video_id: The confirmed video ID.
        preferred_format: The preferred subtitle format (e.g., "vtt").
    """

    youtube_url: str
    actual_video_id: str
    preferred_format: str


class YtdlpLogger:
    """Redirect yt-dlp's internal logging messages to SourceLens's logging system."""

    _node_logger: logging.Logger

    def __init__(self, node_logger: logging.Logger) -> None:
        """Initialize the YtdlpLogger.

        Args:
            node_logger (logging.Logger): The logger instance of the parent node
                to which yt-dlp messages will be redirected.
        """
        self._node_logger = node_logger

    def debug(self, msg: str) -> None:
        """Log debug messages from yt-dlp to the node's logger.

        Removes the "[debug] " prefix added by yt-dlp if present.

        Args:
            msg (str): The debug message string from yt-dlp.
        """
        if msg.startswith("[debug] "):
            self._node_logger.debug("yt-dlp-lib: %s", msg[len("[debug] ") :])
        else:
            self._node_logger.debug("yt-dlp-lib: %s", msg)

    def warning(self, msg: str) -> None:
        """Log warning messages from yt-dlp to the node's logger.

        Args:
            msg (str): The warning message string from yt-dlp.
        """
        self._node_logger.warning("yt-dlp-lib: %s", msg)

    def error(self, msg: str) -> None:
        """Log error messages from yt-dlp to the node's logger.

        Args:
            msg (str): The error message string from yt-dlp.
        """
        self._node_logger.error("yt-dlp-lib: %s", msg)


@dataclass
class VttParseContext:
    """Context for VTT parsing, including video metadata and LLM configurations.

    This dataclass encapsulates all necessary information required by the
    VTT parsing and cleaning logic, including details for constructing
    headers and configurations for any LLM-based processing steps.

    Attributes:
        video_title (str): Title of the video, used for the transcript header.
        original_lang_code (str): Language code of the transcript, for the header.
        youtube_url (Optional[str]): URL of the video, included in the header if available.
        llm_config (LlmConfigDict): Configuration for LLM calls, used for deduplication.
        cache_config (CacheConfigDict): Configuration for LLM caching during deduplication.
    """

    video_title: str
    original_lang_code: str
    youtube_url: Optional[str]
    llm_config: LlmConfigDict
    cache_config: CacheConfigDict


class YouTubeWebVTTCleaner:
    """Clean YouTube WebVTT subtitles for _orig.md generation with basic deduplication.

    This class reads a WebVTT file (or buffer), performs initial cleaning steps
    like removing empty captions and exact duplicates, and then formats the
    content into Markdown with time block headers.
    """

    vtt: "ImportedWebVTT"

    def __init__(self, vtt_input: Union[str, io.StringIO], logger_instance: Optional[logging.Logger] = None) -> None:
        """Initialize the WebVTT cleaner.

        Loads WebVTT content from a file path or an in-memory buffer.

        Args:
            vtt_input: Path to the VTT file (as a string)
                or an `io.StringIO` object containing the VTT content.
            logger_instance: An optional logger instance
                for internal logging within the cleaner. Defaults to None.

        Raises:
            ImportError: If the `webvtt-py` library is not available.
            ValueError: If `vtt_input` is not a string or `io.StringIO` object.
        """
        self.logger: Optional[logging.Logger] = logger_instance
        self.vtt_file_path: Optional[str] = None
        if not WEBVTT_AVAILABLE or webvtt_module is None:  # pragma: no cover
            msg: str = "webvtt-py library is not available. Cannot perform VTT cleaning."
            self._log_message(logging.ERROR, msg)
            raise ImportError(msg)
        if isinstance(vtt_input, str):
            self.vtt_file_path = vtt_input
            self.vtt = webvtt_module.read(vtt_input)
        elif isinstance(vtt_input, io.StringIO):
            self.vtt = webvtt_module.read_buffer(vtt_input)
        else:  # pragma: no cover
            raise ValueError("vtt_input must be str (file path) or io.StringIO object")

    def _log_message(self, level: int, message: str, *args: Any) -> None:
        """Log a message using the provided logger or print as a fallback.

        Args:
            level: The logging level (e.g., `logging.INFO`, `logging.WARNING`).
            message: The message string to log, possibly with format specifiers.
            *args: Optional arguments to be merged into the message string.
        """
        if self.logger:
            self.logger.log(level, message, *args)
        else:  # pragma: no cover
            level_name: str = logging.getLevelName(level)
            formatted_message: str = message % args if args else message
            print(f"{level_name}: {formatted_message}")

    def _find_empty_captions(self) -> list[int]:
        """Find indices of VTT captions that are empty or contain only whitespace.

        Returns:
            A list of integer indices corresponding to empty captions
            within the loaded VTT `self.vtt.captions` list.
        """
        empty_indices: list[int] = []
        for i, caption_item in enumerate(self.vtt.captions):
            normalized_text: str = self._normalize_for_comparison(caption_item.text)
            if not normalized_text.strip():
                empty_indices.append(i)
        return empty_indices

    def _find_exact_duplicates(self) -> list[list[int]]:
        """Find groups of VTT captions that are exactly identical in text and timing.

        Compares captions based on their normalized text content and exact start/end times.

        Returns:
            A list of lists, where each inner list contains the indices
            (relative to `self.vtt.captions`) of a group of
            exactly duplicate captions. Groups with only one caption
            (i.e., no duplicates) are not included.
        """
        content_to_indices_map: dict[tuple[str, str, str], list[int]] = {}
        for i, caption_item in enumerate(self.vtt.captions):
            key_tuple: tuple[str, str, str] = (
                self._normalize_for_comparison(caption_item.text),
                caption_item.start,
                caption_item.end,
            )
            content_to_indices_map.setdefault(key_tuple, []).append(i)
        return [indices for indices in content_to_indices_map.values() if len(indices) > 1]

    def _find_close_text_duplicates(self, max_time_gap_seconds: int = 5) -> list[list[int]]:
        """Find VTT captions that have identical text and are close in time.

        Identifies captions with the same normalized text content whose start times
        are within `max_time_gap_seconds` of each other.

        Args:
            max_time_gap_seconds: The maximum time difference (in seconds)
                between the start times of captions for them to be considered
                "close" textual duplicates. Defaults to 5 seconds.

        Returns:
            A list of lists, where each inner list contains the indices
            (relative to `self.vtt.captions`) of a group of closely
            timed textual duplicates.
        """
        text_to_time_map: dict[str, list[tuple[int, int]]] = {}
        for i, caption_item in enumerate(self.vtt.captions):
            normalized_text: str = self._normalize_for_comparison(caption_item.text)
            start_time_seconds: int = self._time_to_seconds(caption_item.start)
            text_to_time_map.setdefault(normalized_text, []).append((i, start_time_seconds))

        close_duplicate_groups: list[list[int]] = []
        for caption_list_with_times in text_to_time_map.values():
            if len(caption_list_with_times) > 1:
                caption_list_with_times.sort(key=lambda x_item: x_item[1])
                current_group_indices: list[int] = [caption_list_with_times[0][0]]
                for i_item in range(1, len(caption_list_with_times)):
                    current_index, current_start_time = caption_list_with_times[i_item]
                    _previous_index, previous_start_time = caption_list_with_times[i_item - 1]
                    if (
                        current_start_time >= 0
                        and previous_start_time >= 0
                        and abs(current_start_time - previous_start_time) <= max_time_gap_seconds
                    ):
                        current_group_indices.append(current_index)
                    else:
                        if len(current_group_indices) > 1:
                            close_duplicate_groups.append(list(current_group_indices))
                        current_group_indices = [current_index]
                if len(current_group_indices) > 1:
                    close_duplicate_groups.append(list(current_group_indices))
        return close_duplicate_groups

    def clean_for_orig_md(self) -> "ImportedWebVTT":  # type: ignore[name-defined]
        """Perform VTT cleaning optimized for generating the initial _orig.md file.

        This method removes empty captions, exact duplicates (based on text and time),
        and textual duplicates that are very close in time. It retains the first
        occurrence in duplicate groups.

        Returns:
            A new `webvtt.WebVTT` object containing only the cleaned captions.

        Raises:
            RuntimeError: If the `webvtt-py` module is not available when trying to
                          create a new WebVTT object.
        """
        indices_to_remove: set[int] = set(self._find_empty_captions())
        for duplicate_group in self._find_exact_duplicates():
            indices_to_remove.update(duplicate_group[1:])
        for text_duplicate_group in self._find_close_text_duplicates():
            indices_to_remove.update(text_duplicate_group[1:])

        if webvtt_module is None:  # Should be caught by __init__, but as a safeguard
            raise RuntimeError("webvtt module not available for creating WebVTT object.")  # pragma: no cover

        cleaned_vtt_obj: "ImportedWebVTT" = webvtt_module.WebVTT()
        for i, caption_item in enumerate(self.vtt.captions):
            if i not in indices_to_remove:
                cleaned_vtt_obj.captions.append(caption_item)
        return cleaned_vtt_obj

    def generate_orig_md_content(self, context: VttParseContext, time_block_minutes: int = 1) -> str:
        """Generate Markdown content for _orig.md with time blocks from cleaned captions.

        The content includes a header with video title, language, and source URL,
        followed by the VTT text segmented into time blocks.

        Args:
            context: Context object containing `video_title`,
                `original_lang_code`, and `youtube_url` for the header.
            time_block_minutes: The interval (in minutes) for creating
                time block headers (e.g., "#### [MM:SS]"). Defaults to 1 minute.

        Returns:
            A string formatted as Markdown for the _orig.md file.
        """
        cleaned_vtt_obj: "ImportedWebVTT" = self.clean_for_orig_md()
        self._log_cleaning_stats(len(self.vtt.captions), len(cleaned_vtt_obj.captions))

        header_lines_list: list[str] = [f"# Transcript: {context.video_title}"]
        header_info_str: str = f"(Language: {context.original_lang_code}"
        if context.youtube_url:
            header_info_str += f" , Source: {context.youtube_url}"
        header_info_str += " )"
        header_lines_list.extend([header_info_str, ""])

        if not cleaned_vtt_obj.captions:
            header_lines_list.append("No transcript content available after cleaning.")
            return "\n".join(header_lines_list)

        content_parts_buffer: list[str] = list(header_lines_list)
        current_block_start_s: int = -1
        current_block_segments_list: list[str] = []
        last_added_segment_text: Optional[str] = None

        for caption_obj in cleaned_vtt_obj.captions:
            caption_start_seconds: int = self._time_to_seconds(caption_obj.start)
            if caption_start_seconds < 0:
                continue

            block_interval_s: int = time_block_minutes * 60
            expected_block_start_s: int = (caption_start_seconds // block_interval_s) * block_interval_s

            if expected_block_start_s > current_block_start_s:
                if current_block_segments_list:
                    content_parts_buffer.append("\n".join(current_block_segments_list))
                    content_parts_buffer.append("")
                current_block_start_s = expected_block_start_s
                content_parts_buffer.append(f"#### {self._seconds_to_time_header(current_block_start_s)}")
                current_block_segments_list, last_added_segment_text = [], None

            cleaned_text_str_display: str = self._clean_caption_text_for_display(caption_obj.text)
            if cleaned_text_str_display:
                if cleaned_text_str_display != last_added_segment_text:
                    current_block_segments_list.append(cleaned_text_str_display)
                    last_added_segment_text = cleaned_text_str_display
                else:
                    self._log_message(logging.DEBUG, "Deduplicated in generate_orig_md: '%s'", cleaned_text_str_display)
        if current_block_segments_list:
            content_parts_buffer.append("\n".join(current_block_segments_list))
        return "\n".join(content_parts_buffer)

    def _normalize_for_comparison(self, text: str) -> str:
        """Normalize text for comparison (lowercase, no HTML, collapse whitespace).

        Args:
            text: The input text string.

        Returns:
            The normalized text string.
        """
        text_no_html: str = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"\s+", " ", text_no_html).strip().lower()

    def _clean_caption_text_for_display(self, text: str) -> str:
        """Clean caption text for final display (remove HTML, normalize whitespace).

        Args:
            text: The input caption text.

        Returns:
            The cleaned caption text.
        """
        text_no_html: str = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"\s+", " ", text_no_html).strip()

    def _time_to_seconds(self, time_str: str) -> int:
        """Convert WebVTT time string (HH:MM:SS.mmm or MM:SS.mmm) to total seconds.

        Args:
            time_str: The VTT time string (e.g., "00:01:23.456" or "01:23.456").

        Returns:
            Total seconds as an integer. Returns -1 if parsing fails.
        """
        try:
            time_parts: list[str] = time_str.split(":")
            num_parts: int = len(time_parts)
            if num_parts == EXPECTED_VTT_TIME_PARTS:  # HH:MM:SS.mmm
                h_val_s, m_val_s, s_ms_val_s = time_parts
                s_val_s, _ = s_ms_val_s.split(".") if "." in s_ms_val_s else (s_ms_val_s, "0")
                return int(h_val_s) * 3600 + int(m_val_s) * 60 + int(s_val_s)
            if num_parts == EXPECTED_VTT_SEC_MILLISECOND_PARTS:  # MM:SS.mmm
                m_val_s, s_ms_val_s = time_parts
                s_val_s, _ = s_ms_val_s.split(".") if "." in s_ms_val_s else (s_ms_val_s, "0")
                return int(m_val_s) * 60 + int(s_val_s)
            raise ValueError(f"Invalid VTT time format component count: {num_parts}")  # pragma: no cover
        except (ValueError, IndexError, AttributeError) as e_time_parse:
            self._log_message(logging.WARNING, "Error parsing VTT time string '%s': %s", time_str, e_time_parse)
            return -1

    def _seconds_to_time_header(self, seconds: int) -> str:
        """Convert total seconds to [MM:SS] format for time block headers.

        Args:
            seconds: Total seconds from the start of the video.

        Returns:
            A string formatted as "[MM:SS]". Returns "[??:??]" if input seconds is negative.
        """
        if seconds < 0:
            return "[??:??]"
        minutes_val: int = seconds // 60
        seconds_remainder: int = seconds % 60
        return f"[{minutes_val:02d}:{seconds_remainder:02d}]"

    def _log_cleaning_stats(self, original_caption_count: int, cleaned_caption_count: int) -> None:
        """Log statistics about the VTT caption cleaning process.

        Args:
            original_caption_count: Number of captions before cleaning.
            cleaned_caption_count: Number of captions after cleaning.
        """
        removed_captions_count: int = original_caption_count - cleaned_caption_count
        if removed_captions_count > 0:
            self._log_message(
                logging.INFO,
                f"WebVTT cleaning: Removed {removed_captions_count} captions from {original_caption_count} total.",
            )
        else:
            self._log_message(
                logging.DEBUG, f"WebVTT cleaning: No captions removed. Original count: {original_caption_count}."
            )


class FetchYouTubeContent(BaseNode[FetchYouTubeContentPreparedInputsYtdlp, FetchYouTubeContentExecutionResultYtdlp]):
    """Fetch YouTube video transcripts and metadata using the yt-dlp library."""

    _yt_dlp_custom_logger: YtdlpLogger
    _DOWNLOAD_AUDIO_MP3_SECRET_FEATURE_ENABLED: Final[bool] = _DOWNLOAD_AUDIO_MP3_SECRET_FEATURE_ENABLED

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the FetchYouTubeContent node.

        Sets up retry parameters for the node's execution phase and initializes a
        custom logger to capture output from the yt-dlp library.

        Args:
            max_retries: Maximum number of retries for the `execution` phase.
                         If 0, only the initial attempt is made.
            wait: Wait time in seconds between retries for the `execution` phase.
        """
        super().__init__(max_retries=max_retries, wait=wait)
        self._yt_dlp_custom_logger = YtdlpLogger(self._logger)

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract the 11-character YouTube video ID from various URL formats.

        Iterates through known YouTube URL patterns to find and return the video ID.

        Args:
            url: The YouTube URL string to parse.

        Returns:
            The extracted video ID as a string if found, otherwise None.
        """
        if not url:
            return None
        for pattern_re_obj in YOUTUBE_URL_PATTERNS_NODE_YTDLP:
            match_re_obj: Optional[re.Match[str]] = pattern_re_obj.search(url)
            if match_re_obj:
                return match_re_obj.group(1)
        return None

    def _get_video_metadata_with_yt_dlp(
        self, youtube_url: str, video_id_for_log: str, shared_context: SLSharedContext
    ) -> Optional[VideoMetadata]:
        """Fetch and parse video metadata using yt-dlp's info extraction.

        Updates `shared_context` with the fetched video ID, title, and sanitized title.
        This method is crucial for determining available subtitles and other video details
        before attempting to download any content.

        Args:
            youtube_url: The URL of the YouTube video.
            video_id_for_log: The video ID (pre-extracted or from context) used for logging.
            shared_context: The shared context dictionary to update with fetched metadata.

        Returns:
            A `VideoMetadata` dataclass instance containing extracted information
            if successful, otherwise None if yt-dlp is unavailable or an error occurs.
        """
        if not YTDLP_AVAILABLE or yt_dlp_module is None:  # pragma: no cover
            self._log_warning("yt-dlp module is not available; cannot fetch video metadata.")
            return None

        ydl_options: YdlOpts = {
            "logger": self._yt_dlp_custom_logger,
            "quiet": False,
            "no_warnings": False,
            "verbose": True,
            "skip_download": True,
            "extract_flat": False,
            "noplaylist": True,
        }
        self._log_debug("Attempting to extract video info with yt-dlp options: %s", ydl_options)
        try:
            with yt_dlp_module.YoutubeDL(ydl_options) as ydl_instance:
                info_data: YdlInfoDict = ydl_instance.extract_info(youtube_url, download=False)

            actual_video_id_val: str = str(info_data.get("id", video_id_for_log))
            video_title_str: str = str(info_data.get("title", f"YouTube Video: {actual_video_id_val}"))
            shared_context["current_youtube_video_id"] = actual_video_id_val
            shared_context["current_youtube_video_title"] = video_title_str
            shared_context["current_youtube_sanitized_title"] = sanitize_filename(video_title_str)

            video_description_val: Optional[str] = cast(Optional[str], info_data.get("description"))
            upload_date_val: Optional[str] = cast(Optional[str], info_data.get("upload_date"))
            view_count_val: Any = info_data.get("view_count")
            view_count_int: Optional[int] = int(view_count_val) if isinstance(view_count_val, int) else None
            uploader_name_val: Optional[str] = cast(Optional[str], info_data.get("uploader"))

            self._log_debug("yt-dlp info_dict for video '%s' (Title: '%s')", actual_video_id_val, video_title_str)
            manual_subs_data_val: dict[str, Any] = info_data.get("subtitles", {}) or {}
            auto_subs_data_val: dict[str, Any] = info_data.get("automatic_captions", {}) or {}
            self._log_debug("Available manual subtitles: %s", list(manual_subs_data_val.keys()))
            self._log_debug("Available automatic_captions: %s", list(auto_subs_data_val.keys()))

            return VideoMetadata(
                id=actual_video_id_val,
                title=video_title_str,
                description=video_description_val,
                upload_date=upload_date_val,
                view_count=view_count_int,
                uploader=uploader_name_val,
                available_manual_langs=sorted(manual_subs_data_val.keys()),
                available_auto_langs=sorted(auto_subs_data_val.keys()),
                raw_subtitles_info=manual_subs_data_val,
                raw_auto_captions_info=auto_subs_data_val,
            )
        except (YtdlpDownloadError, YtdlpExtractorError, YtdlpUnavailableVideoError) as e_yt_dlp_err:  # type: ignore[misc]
            self._log_error("yt-dlp error during info extraction for %s: %s", video_id_for_log, e_yt_dlp_err)
        except RuntimeError as e_runtime_err_yt:  # pragma: no cover
            self._log_error(
                "Runtime error during yt-dlp info for %s: %s", video_id_for_log, e_runtime_err_yt, exc_info=True
            )
        except ValueError as e_value_err_yt:
            self._log_error(
                "ValueError during yt-dlp info processing for %s: %s", video_id_for_log, e_value_err_yt, exc_info=True
            )
        return None

    def _build_subtitle_attempt_order(
        self, metadata: VideoMetadata, expected_langs: list[str], *, prefer_manual: bool, fallback_auto: bool
    ) -> list[SubtitleAttemptTarget]:
        """Build the prioritized list of (language, type) for subtitle download attempts.

        The order is determined by iterating through `expected_langs` and applying
        preferences for `prefer_manual` subtitles and `fallback_auto` to ASR captions.

        Args:
            metadata: Extracted video metadata containing lists of available
                manual and automatic subtitle languages.
            expected_langs: A list of preferred language codes (e.g., ["en", "sk"])
                in order of preference.
            prefer_manual: If True, manual subtitles are preferred over automatic ones
                for a given language.
            fallback_auto: If True and no manual subtitle is found for a preferred
                language (and `prefer_manual` is True), or if `prefer_manual` is False,
                an attempt will be made for an automatic subtitle in that language.

        Returns:
            An ordered list of `SubtitleAttemptTarget` objects, representing the
            sequence in which different language/type combinations should be attempted
            for download. Each target is unique.
        """
        attempt_order_list_obj: list[SubtitleAttemptTarget] = []
        self._log_debug(
            "Building subtitle attempt order. Preferred: %s. Manual available: %s. Auto available: %s.",
            expected_langs,
            metadata.available_manual_langs,
            metadata.available_auto_langs,
        )
        for lang_code_str_val_item in expected_langs:
            manual_is_available_flag: bool = lang_code_str_val_item in metadata.available_manual_langs
            auto_is_available_flag: bool = lang_code_str_val_item in metadata.available_auto_langs

            if prefer_manual:
                if manual_is_available_flag:
                    attempt_order_list_obj.append(
                        SubtitleAttemptTarget(lang_code=lang_code_str_val_item, type=SubtitleType.MANUAL)
                    )
                if fallback_auto and auto_is_available_flag and not manual_is_available_flag:
                    attempt_order_list_obj.append(
                        SubtitleAttemptTarget(lang_code=lang_code_str_val_item, type=SubtitleType.AUTOMATIC)
                    )
            else:
                if fallback_auto and auto_is_available_flag:
                    attempt_order_list_obj.append(
                        SubtitleAttemptTarget(lang_code=lang_code_str_val_item, type=SubtitleType.AUTOMATIC)
                    )
                if manual_is_available_flag and not auto_is_available_flag:
                    attempt_order_list_obj.append(
                        SubtitleAttemptTarget(lang_code=lang_code_str_val_item, type=SubtitleType.MANUAL)
                    )

        final_unique_attempts_list: list[SubtitleAttemptTarget] = []
        seen_targets_set_obj: set[tuple[str, SubtitleType]] = set()
        for attempt_item_val_obj in attempt_order_list_obj:
            target_tuple_val_obj: tuple[str, SubtitleType] = (attempt_item_val_obj.lang_code, attempt_item_val_obj.type)
            if target_tuple_val_obj not in seen_targets_set_obj:
                final_unique_attempts_list.append(attempt_item_val_obj)
                seen_targets_set_obj.add(target_tuple_val_obj)
        self._log_debug("Determined subtitle download attempt order: %s", final_unique_attempts_list)
        return final_unique_attempts_list

    def _deduplicate_transcript_with_llm(self, initial_transcript_content: str, parse_ctx: VttParseContext) -> str:
        """Perform advanced deduplication on transcript text using an LLM.

        This method takes transcript text (expected to still contain time blocks)
        and uses an LLM to clean it by removing various types of repetitions,
        while aiming to preserve the time blocks and original language.

        Args:
            initial_transcript_content (str): The transcript text to be deduplicated.
                                              It should include time block headers.
            parse_ctx (VttParseContext): Context object containing LLM configurations
                                         and other info needed for the prompt.

        Returns:
            str: The LLM-cleaned transcript text, ideally with time blocks preserved.
                 If LLM call fails or returns empty, returns the original
                 `initial_transcript_content`.
        """
        if not initial_transcript_content.strip():
            self._log_warning("LLM deduplication input is empty. Returning as is.")
            return initial_transcript_content

        self._log_info(
            "Attempting LLM-based advanced deduplication of original transcript (lang: %s).",
            parse_ctx.original_lang_code,
        )
        deduplication_llm_prompt_str_val: str = (
            OriginalTranscriptDeduplicationPrompts.format_deduplicate_transcript_prompt(
                text_to_clean=initial_transcript_content
            )
        )
        try:
            llm_cleaned_text_output_val: str = call_llm(
                deduplication_llm_prompt_str_val, parse_ctx.llm_config, parse_ctx.cache_config
            )
            if llm_cleaned_text_output_val.strip():
                self._log_info("LLM successfully deduplicated original transcript text.")
                # Header is expected to be added by generate_orig_md_content or re-added later
                # This method just returns the LLM's attempt at cleaning the body + timecodes
                return llm_cleaned_text_output_val.strip()

            # LLM returned empty content
            self._log_warning("LLM deduplication returned empty content. Using input text instead.")  # pragma: no cover
            return initial_transcript_content  # pragma: no cover
        except LlmApiError as e_llm_api_err_dedup:
            self._log_error(
                "LLM call for original transcript deduplication failed: %s. Using input text for further processing.",
                e_llm_api_err_dedup,
            )
            return initial_transcript_content
        except (TypeError, ValueError) as e_proc_err_dedup:  # pragma: no cover
            self._log_error(
                "Unexpected error processing LLM transcript deduplication output: %s. "
                "Using input text for further processing.",
                e_proc_err_dedup,
                exc_info=True,
            )
            return initial_transcript_content

    def _parse_vtt_to_plain_text(self, vtt_content_str: str, parse_ctx: VttParseContext) -> str:
        """Extract, clean, and format plain text from VTT content, including LLM deduplication.

        This method orchestrates VTT parsing:
        1. Uses `YouTubeWebVTTCleaner` for initial cleaning and time block generation.
        2. Calls an LLM via `_deduplicate_transcript_with_llm` for advanced
           deduplication of the transcript text, while aiming to preserve time blocks.
        3. Ensures a standard Markdown header is prepended to the final text.

        Args:
            vtt_content_str: The raw string content of the VTT file.
            parse_ctx: A `VttParseContext` object containing video title, language codes,
                       YouTube URL, and LLM/cache configurations.

        Returns:
            The cleaned and formatted transcript text as a string. This text includes
            `#### [MM:SS]` time block headers and should have undergone LLM-enhanced
            deduplication if that step was successful.
        """
        self._log_debug("Initial VTT parsing and cleaning using YouTubeWebVTTCleaner.")
        initial_md_content_vtt_cleaned_str: str
        if WEBVTT_AVAILABLE and webvtt_module is not None:
            try:
                vtt_cleaner_obj_instance = YouTubeWebVTTCleaner(
                    io.StringIO(vtt_content_str), logger_instance=self._logger
                )
                initial_md_content_vtt_cleaned_str = vtt_cleaner_obj_instance.generate_orig_md_content(
                    context=parse_ctx, time_block_minutes=1
                )
            except (ImportError, ValueError) as e_vtt_cleaner_init_err:  # pragma: no cover
                self._log_error(
                    "YouTubeWebVTTCleaner initialization failed: %s. Falling back to regex VTT parsing.",
                    e_vtt_cleaner_init_err,
                    exc_info=True,
                )
                initial_md_content_vtt_cleaned_str = self._parse_vtt_to_plain_text_regex_fallback(
                    vtt_content_str, parse_ctx.video_title, parse_ctx.original_lang_code, parse_ctx.youtube_url
                )
            except Exception as e_vtt_unknown_proc_err:  # pragma: no cover  # noqa: BLE001
                self._log_error(
                    "Unexpected error during YouTubeWebVTTCleaner processing: %s. Falling back to regex VTT parsing.",
                    type(e_vtt_unknown_proc_err).__name__,
                    exc_info=True,
                )
                initial_md_content_vtt_cleaned_str = self._parse_vtt_to_plain_text_regex_fallback(
                    vtt_content_str, parse_ctx.video_title, parse_ctx.original_lang_code, parse_ctx.youtube_url
                )
        else:  # pragma: no cover
            self._log_warning("webvtt-py library not available. Using regex fallback for VTT parsing.")
            initial_md_content_vtt_cleaned_str = self._parse_vtt_to_plain_text_regex_fallback(
                vtt_content_str, parse_ctx.video_title, parse_ctx.original_lang_code, parse_ctx.youtube_url
            )

        # Now, pass the VTT cleaner's output (which includes a header) to LLM deduplication
        llm_deduplicated_content: str = self._deduplicate_transcript_with_llm(
            initial_md_content_vtt_cleaned_str, parse_ctx
        )

        # Ensure the final content has the correct header, as LLM might strip/alter it.
        # _deduplicate_transcript_with_llm already attempts to re-add header if LLM removed it.
        return llm_deduplicated_content  # This should already have the header

    def _parse_vtt_to_plain_text_regex_fallback(
        self, vtt_content_str: str, video_title_str: str, original_lang_code_str: str, youtube_url_str: Optional[str]
    ) -> str:
        """Provide a fallback VTT parser using regex if `webvtt-py` is unavailable or fails.

        This method performs basic cleaning, attempts to create time block headers,
        and does a simple line-by-line deduplication.

        Args:
            vtt_content_str: The raw string content of the VTT file.
            video_title_str: Title of the video, used for the transcript header.
            original_lang_code_str: Language code of the transcript, for the header.
            youtube_url_str: URL of the video, for the header.

        Returns:
            The cleaned transcript text, formatted with `#### [MM:SS]` time block headers.
        """
        self._log_warning("Using regex-based VTT parsing fallback with line-by-line deduplication.")
        if not vtt_content_str.strip():
            header_fb_lines_list_val: list[str] = [
                f"# Transcript: {video_title_str}",
                f"(Language: {original_lang_code_str}",
            ]
            if youtube_url_str:
                header_fb_lines_list_val[1] += f" , Source: {youtube_url_str}"
            header_fb_lines_list_val[1] += " )"
            header_fb_lines_list_val.append("\n\nNo transcript content available.")
            return "\n".join(header_fb_lines_list_val)

        content_no_header_text_val: str = self._clean_vtt_header_and_metadata_blocks_regex(vtt_content_str)
        original_text_lines_list_val: list[str] = content_no_header_text_val.splitlines()
        processed_transcript_lines_list_val: list[str] = self._process_vtt_lines_for_time_blocks_regex(
            original_text_lines_list_val
        )

        final_output_parts_list_val: list[str] = [
            f"# Transcript: {video_title_str}",
            f"(Language: {original_lang_code_str}",
        ]
        if youtube_url_str:
            final_output_parts_list_val[1] += f" , Source: {youtube_url_str}"
        final_output_parts_list_val[1] += " )"
        final_output_parts_list_val.extend(["", *processed_transcript_lines_list_val])
        return "\n".join(final_output_parts_list_val).strip()

    def _clean_vtt_header_and_metadata_blocks_regex(self, vtt_content: str) -> str:
        """Remove WEBVTT header, Kind, Language, NOTE, and STYLE blocks from VTT content.

        This is a helper for the regex-based VTT parsing fallback.

        Args:
            vtt_content: The raw string content of the VTT file.

        Returns:
            The VTT content with common header and metadata blocks removed.
        """
        content_str_val: str = re.sub(r"^WEBVTT.*?\n(\r\n|\n)?", "", vtt_content, count=1, flags=re.MULTILINE)
        content_str_val = re.sub(r"^(Kind|Language):.*?\n(\r\n|\n)?", "", content_str_val, flags=re.MULTILINE)
        clean_lines_list_val: list[str] = []
        in_skip_block_flag_val: bool = False
        for line_item_val_str in content_str_val.splitlines():  # pragma: no cover
            stripped_line_val: str = line_item_val_str.strip()
            if stripped_line_val.startswith("NOTE") or stripped_line_val.startswith("STYLE"):
                in_skip_block_flag_val = True
                continue
            if in_skip_block_flag_val and not stripped_line_val:
                in_skip_block_flag_val = False
                continue
            if not in_skip_block_flag_val:
                clean_lines_list_val.append(line_item_val_str)
        return "\n".join(clean_lines_list_val)

    def _handle_vtt_timestamp_line_for_dedup_regex(  # pragma: no cover
        self,
        line_content_str_val: str,
        processed_lines_list_val: list[str],
        current_minute_header_str_val: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle a VTT timestamp line for the regex-based deduplication logic.

        Identifies minute markers and adds time block headers.

        Args:
            line_content_str_val: Current line being processed, expected to be a timestamp line.
            processed_lines_list_val: List of already processed (output) lines.
            current_minute_header_str_val: Header string of the current minute block.

        Returns:
            A tuple containing the (potentially updated minute_block_header,
            None (as last_added_text is reset for a new time block)).
        """
        timestamp_match_obj_val: Optional[re.Match[str]] = re.match(
            r"^(\d{2}):(\d{2}):\d{2}\.\d{3}\s*-->", line_content_str_val
        )
        if not timestamp_match_obj_val:
            return current_minute_header_str_val, None

        hours_str_item: str
        minutes_str_item: str
        hours_str_item, minutes_str_item = timestamp_match_obj_val.group(1), timestamp_match_obj_val.group(2)
        new_time_header_str_val: str = f"#### [{hours_str_item}:{minutes_str_item}]"
        updated_minute_header_str_val: Optional[str] = current_minute_header_str_val

        if new_time_header_str_val != current_minute_header_str_val:
            if (
                processed_lines_list_val
                and processed_lines_list_val[-1].strip()
                and not processed_lines_list_val[-1].startswith("#### [")
            ):
                processed_lines_list_val.append("")
            processed_lines_list_val.append(new_time_header_str_val)
            updated_minute_header_str_val = new_time_header_str_val
        return updated_minute_header_str_val, None

    def _handle_vtt_text_line_for_dedup_regex(  # pragma: no cover
        self,
        cleaned_text_line_str_val: str,
        processed_lines_list_val: list[str],
        current_minute_header_str_val: Optional[str],
        last_added_text_line_str_val: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle a VTT text line for the regex-based deduplication logic.

        Adds a default time block header if none exists. Appends the cleaned text line
        if it's different from the previously added text line.

        Args:
            cleaned_text_line_str_val: The cleaned (tags removed, stripped) text line.
            processed_lines_list_val: The list of already processed (output) lines.
            current_minute_header_str_val: The header string of the current minute block.
            last_added_text_line_str_val: The last actual text line that was added.

        Returns:
            A tuple containing the (potentially updated minute_block_header,
            potentially updated last_added_text_line).
        """
        updated_minute_header_val: Optional[str] = current_minute_header_str_val
        updated_last_text_val: Optional[str] = last_added_text_line_str_val

        if not updated_minute_header_val and not any(
            pl_item_str.startswith("#### [") for pl_item_str in processed_lines_list_val
        ):
            processed_lines_list_val.append("#### [00:00]")
            updated_minute_header_val = "#### [00:00]"
            updated_last_text_val = None

        if cleaned_text_line_str_val != updated_last_text_val:
            processed_lines_list_val.append(cleaned_text_line_str_val)
            updated_last_text_val = cleaned_text_line_str_val
        else:
            self._log_debug("Deduplicated line (regex fallback): '%s'", cleaned_text_line_str_val)
        return updated_minute_header_val, updated_last_text_val

    def _process_vtt_lines_for_time_blocks_regex(self, vtt_lines_list_val: list[str]) -> list[str]:  # pragma: no cover
        """Process VTT content lines for regex fallback method.

        Creates time block headers and performs simple line-by-line deduplication
        of text content.

        Args:
            vtt_lines_list_val: List of VTT content lines after initial header/metadata
                                block removal.

        Returns:
            A list of processed lines, including time block headers and
            deduplicated text lines.
        """
        output_lines_buffer: list[str] = []
        current_time_header_str_val: Optional[str] = None
        last_actual_text_added_str_val: Optional[str] = None

        for i_line_idx_val, line_text_content_item_val in enumerate(vtt_lines_list_val):
            is_cue_id1_bool_val: bool = bool(
                re.fullmatch(r"^\s*[\w-]+\s*$", line_text_content_item_val)
                and i_line_idx_val + 1 < len(vtt_lines_list_val)
                and re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->", vtt_lines_list_val[i_line_idx_val + 1])
            )
            is_cue_id2_bool_val: bool = bool(
                re.fullmatch(r"^\s*\d+\s*$", line_text_content_item_val)
                and i_line_idx_val + 1 < len(vtt_lines_list_val)
                and re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->", vtt_lines_list_val[i_line_idx_val + 1])
            )
            if is_cue_id1_bool_val or is_cue_id2_bool_val:
                continue

            if re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->", line_text_content_item_val):
                current_time_header_str_val, last_actual_text_added_str_val = (
                    self._handle_vtt_timestamp_line_for_dedup_regex(
                        line_text_content_item_val, output_lines_buffer, current_time_header_str_val
                    )
                )
                continue

            cleaned_text_val_str: str = re.sub(r"<[^>]*>", "", line_text_content_item_val).strip()
            cleaned_text_val_str = (
                cleaned_text_val_str.replace(" ", " ").replace("<", "<").replace(">", ">").replace("&", "&")
            )

            if cleaned_text_val_str:
                current_time_header_str_val, last_actual_text_added_str_val = (
                    self._handle_vtt_text_line_for_dedup_regex(
                        cleaned_text_val_str,
                        output_lines_buffer,
                        current_time_header_str_val,
                        last_actual_text_added_str_val,
                    )
                )

        final_lines_output_list_val: list[str] = []
        for i_final_idx_item, final_line_item_val in enumerate(output_lines_buffer):
            is_header_line_bool_val: bool = final_line_item_val.startswith("#### [")
            is_last_line_bool_val: bool = i_final_idx_item == len(output_lines_buffer) - 1
            next_is_hdr_or_empty_bool_val: bool = not is_last_line_bool_val and (
                output_lines_buffer[i_final_idx_item + 1].startswith("#### [")
                or not output_lines_buffer[i_final_idx_item + 1].strip()
            )

            if is_header_line_bool_val and (is_last_line_bool_val or next_is_hdr_or_empty_bool_val):
                self._log_debug("Skipping empty time block header (regex fallback): %s", final_line_item_val)
                continue
            final_lines_output_list_val.append(final_line_item_val)
        return final_lines_output_list_val

    def pre_execution(self, shared_context: SLSharedContext) -> FetchYouTubeContentPreparedInputsYtdlp:
        """Prepare inputs for fetching YouTube content using yt-dlp.

        This method initializes necessary keys in the `shared_context`, extracts
        video ID and title if not already present (e.g., from CLI arguments),
        and gathers all required configuration parameters for the `execution` phase.

        Args:
            shared_context: The shared context dictionary, which may
                contain pre-filled YouTube information from CLI or previous runs.

        Returns:
            A dictionary containing all parameters needed for the `execution`
            method. If essential prerequisites are not met (e.g., no YouTube URL,
            yt-dlp not available), it returns a dictionary with `{"skip": True}`.
        """
        self._log_info("Preparing for YouTube content (transcript & metadata) fetching using yt-dlp.")
        youtube_keys_to_initialize_list: list[str] = [
            "youtube_processed_successfully",
            "current_youtube_video_id",
            "current_youtube_original_lang",
            "current_youtube_standalone_transcript_path",
            "current_youtube_video_title",
            "current_youtube_url",
            "current_youtube_sanitized_title",
            "current_youtube_description",
            "current_youtube_upload_date",
            "current_youtube_view_count",
            "current_youtube_original_transcript_text",
            "current_youtube_uploader",
            "current_youtube_final_transcript_lang",
            "current_youtube_final_transcript_path",
            "current_youtube_audio_path",
            "cli_extract_audio_enabled",
        ]
        for key_to_init_val in youtube_keys_to_initialize_list:
            default_init_val: Any = False
            if key_to_init_val not in ("youtube_processed_successfully", "cli_extract_audio_enabled"):
                default_init_val = None
            shared_context.setdefault(key_to_init_val, default_init_val)

        if not YTDLP_AVAILABLE or yt_dlp_module is None:  # pragma: no cover
            return {"skip": True, "reason": "yt-dlp library not installed."}

        youtube_crawl_url_any_val_obj: Any = shared_context.get("crawl_url")
        if not isinstance(youtube_crawl_url_any_val_obj, str) or not youtube_crawl_url_any_val_obj:  # pragma: no cover
            return {"skip": True, "reason": "No crawl_url provided for YouTube processing."}
        shared_context["current_youtube_url"] = youtube_crawl_url_any_val_obj

        video_id_from_ctx_val: Optional[str] = cast(Optional[str], shared_context.get("current_youtube_video_id"))
        video_title_from_ctx_val: Optional[str] = cast(Optional[str], shared_context.get("current_youtube_video_title"))
        sanitized_title_from_ctx_val: Optional[str] = cast(
            Optional[str], shared_context.get("current_youtube_sanitized_title")
        )

        if not video_id_from_ctx_val:
            video_id_from_ctx_val = self._extract_video_id(youtube_crawl_url_any_val_obj)
            if not video_id_from_ctx_val:
                return {"skip": True, "reason": "Invalid YouTube URL or ID extraction failed."}  # pragma: no cover
            shared_context["current_youtube_video_id"] = video_id_from_ctx_val
            self._log_info("Extracted video_id '%s' in pre_execution.", video_id_from_ctx_val)

        if not video_title_from_ctx_val or not sanitized_title_from_ctx_val:
            self._log_info(
                "Title/sanitized_title for video ID '%s' missing in context. Will be fetched.",
                video_id_from_ctx_val or "Unknown",
            )

        video_id_asserted_str_val: str = cast(str, video_id_from_ctx_val)
        self._log_info(
            "FetchYouTubeContent targeting ID: %s from URL: %s",
            video_id_asserted_str_val,
            youtube_crawl_url_any_val_obj,
        )

        config_main_dict_val: dict[str, Any] = cast(dict, self._get_required_shared(shared_context, "config"))
        youtube_config_dict_val_obj: dict[str, Any] = config_main_dict_val.get("FL02_web_crawling", {}).get(
            "youtube_processing", {}
        )

        project_name_str_value: str = str(shared_context.get("project_name", f"yt_run_{video_id_asserted_str_val}"))
        output_dir_base_path_str_val: str = str(shared_context.get("output_dir", "output"))
        run_specific_output_path_obj: Path = Path(output_dir_base_path_str_val) / project_name_str_value

        llm_config_data_any_val: Any = self._get_required_shared(shared_context, "llm_config")
        cache_config_data_any_val: Any = self._get_required_shared(shared_context, "cache_config")

        prepared_inputs_dict_val: FetchYouTubeContentPreparedInputsYtdlp = {
            "skip": False,
            "video_id": video_id_asserted_str_val,
            "video_title_from_context": video_title_from_ctx_val,
            "sanitized_video_title_from_context": sanitized_title_from_ctx_val,
            "run_specific_output_dir": run_specific_output_path_obj,
            "youtube_url": youtube_crawl_url_any_val_obj,
            "expected_transcript_languages_on_yt": list(
                youtube_config_dict_val_obj.get("expected_transcript_languages_on_yt", ["en"])
            ),
            "prefer_manual_over_auto": bool(
                youtube_config_dict_val_obj.get("prefer_manual_over_auto", HARDCODED_PREFER_MANUAL_OVER_AUTO)
            ),
            "fallback_to_auto_captions": bool(
                youtube_config_dict_val_obj.get("fallback_to_auto_captions", HARDCODED_FALLBACK_TO_AUTO_CAPTIONS)
            ),
            "preferred_subtitle_download_format": str(
                youtube_config_dict_val_obj.get(
                    "preferred_subtitle_download_format", HARDCODED_PREFERRED_SUBTITLE_DOWNLOAD_FORMAT
                )
            ),
            "save_standalone_transcript": bool(
                youtube_config_dict_val_obj.get("save_standalone_transcript", HARDCODED_SAVE_STANDALONE_TRANSCRIPT)
            ),
            "standalone_transcript_format": str(
                youtube_config_dict_val_obj.get("standalone_transcript_format", HARDCODED_STANDALONE_TRANSCRIPT_FORMAT)
            ),
            "shared_context_ref": shared_context,
            "llm_config": llm_config_data_any_val if isinstance(llm_config_data_any_val, dict) else {},
            "cache_config": cache_config_data_any_val if isinstance(cache_config_data_any_val, dict) else {},
        }
        return prepared_inputs_dict_val

    def _handle_cli_process_output(self, process: "subprocess.Popen[str]") -> None:
        """Log stdout and stderr from the yt-dlp CLI process.

        Args:
            process: The Popen object for the CLI process.
        """
        stdout_str_val, stderr_str_val = process.communicate(timeout=CLI_DOWNLOAD_TIMEOUT_SECONDS)
        if stdout_str_val:  # pragma: no cover
            for line_out_str_item_val in stdout_str_val.splitlines():
                self._yt_dlp_custom_logger.debug(f"CLI_STDOUT: {line_out_str_item_val}")
        if stderr_str_val:  # pragma: no cover
            for line_err_str_item_val in stderr_str_val.splitlines():
                err_line_lower_str_val: str = line_err_str_item_val.lower()
                log_level_for_err_item: int
                if "error" in err_line_lower_str_val:
                    log_level_for_err_item = logging.ERROR
                elif "warning" in err_line_lower_str_val:
                    log_level_for_err_item = logging.WARNING
                else:
                    log_level_for_err_item = logging.DEBUG
                # Use specific logger methods instead of generic .log()
                if log_level_for_err_item == logging.ERROR:
                    self._yt_dlp_custom_logger.error(f"CLI_STDERR: {line_err_str_item_val}")
                elif log_level_for_err_item == logging.WARNING:
                    self._yt_dlp_custom_logger.warning(f"CLI_STDERR: {line_err_str_item_val}")
                else:
                    self._yt_dlp_custom_logger.debug(f"CLI_STDERR: {line_err_str_item_val}")

    def _download_subtitles_via_cli(
        self, params: CliDownloadParams, target: SubtitleAttemptTarget
    ) -> tuple[bool, Optional[Path]]:
        """Download subtitles using yt-dlp CLI as a fallback.

        Args:
            params: Parameters for CLI download, including temp path and video info.
            target: The specific language and type of subtitle to download.

        Returns:
            A tuple indicating success (True/False) and
            the `Path` to the downloaded file if successful, else None.
        """
        sub_type_cli_arg_str_val: str = "--write-auto-subs" if target.type == SubtitleType.AUTOMATIC else "--write-sub"
        output_template_cli_str_val_item: str = str(params.temp_dir_path / f"{params.actual_video_id}.%(ext)s")
        expected_file_cli_path_obj_val: Path = (
            params.temp_dir_path / f"{params.actual_video_id}.{target.lang_code}.{params.preferred_format}"
        )
        command_list_cli_val_list: list[str] = [
            "yt-dlp",
            sub_type_cli_arg_str_val,
            "--sub-lang",
            target.lang_code,
            "--sub-format",
            params.preferred_format,
            "--skip-download",
            "--no-warnings",
            "--output",
            output_template_cli_str_val_item,
            params.youtube_url,
        ]
        self._log_info("Executing yt-dlp CLI (fallback): %s", " ".join(command_list_cli_val_list))
        creation_flags_val_int_item: int = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        try:
            cli_process_obj_val: subprocess.Popen[str] = subprocess.Popen(
                command_list_cli_val_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=creation_flags_val_int_item,
            )
            self._handle_cli_process_output(cli_process_obj_val)
            if cli_process_obj_val.returncode == 0:
                if expected_file_cli_path_obj_val.is_file() and expected_file_cli_path_obj_val.stat().st_size > 0:
                    self._log_info(
                        "yt-dlp CLI success: file %s for lang %s, type %s.",
                        expected_file_cli_path_obj_val.name,
                        target.lang_code,
                        target.type.value,
                    )
                    return True, expected_file_cli_path_obj_val
                alt_file_cli_path_obj_val: Path = (
                    params.temp_dir_path / f"{params.actual_video_id}.{params.preferred_format}"
                )
                if (
                    alt_file_cli_path_obj_val.is_file() and alt_file_cli_path_obj_val.stat().st_size > 0
                ):  # pragma: no cover
                    self._log_info("Found CLI subtitle file with alt name: %s", alt_file_cli_path_obj_val)
                    return True, alt_file_cli_path_obj_val
                self._log_warning(
                    "yt-dlp CLI OK, but file %s not found/empty.", expected_file_cli_path_obj_val
                )  # pragma: no cover
                return False, None
            self._log_error(
                "yt-dlp CLI failed (code %s) for lang %s, type %s.",  # pragma: no cover
                cli_process_obj_val.returncode,
                target.lang_code,
                target.type.value,
            )
            return False, None
        except subprocess.TimeoutExpired:  # pragma: no cover
            self._log_error("yt-dlp CLI timed out for lang %s, type %s.", target.lang_code, target.type.value)
        except FileNotFoundError:  # pragma: no cover
            self._log_error("yt-dlp command not found. Ensure it is in PATH.")
        except (OSError, ValueError) as e_subprocess_err_val_item:  # pragma: no cover
            self._log_error(
                "Subprocess error for lang %s, type %s: %s",
                target.lang_code,
                target.type.value,
                e_subprocess_err_val_item,
                exc_info=True,
            )
        return False, None

    def _attempt_library_download(self, params: LibraryDownloadParams, target: SubtitleAttemptTarget) -> Optional[Path]:
        """Attempt subtitle download using yt-dlp as a Python library.

        Args:
            params: Parameters for library download, including temp path and video info.
            target: The specific language and type of subtitle to download.

        Returns:
            The `Path` to the downloaded file if successful, otherwise None.
        """
        if not yt_dlp_module:
            return None  # pragma: no cover
        self._log_info("Attempting lib download for lang '%s', type '%s'.", target.lang_code, target.type.value)
        ydl_options_lib_dict_val: YdlOpts = {
            "writesubtitles": target.type == SubtitleType.MANUAL,
            "writeautomaticsubs": target.type == SubtitleType.AUTOMATIC,
            "subtitleslangs": [target.lang_code],
            "subtitlesformat": params.preferred_format,
            "skip_download": True,
            "noplaylist": True,
            "logger": self._yt_dlp_custom_logger,
            "quiet": False,
            "no_warnings": False,
            "verbose": True,
            "outtmpl": str(params.temp_dir_path / f"{params.actual_video_id}.%(ext)s"),
            "restrictfilenames": True,
        }
        self._log_debug("yt-dlp lib opts for download: %s", json.dumps(ydl_options_lib_dict_val, default=str))
        try:
            with yt_dlp_module.YoutubeDL(ydl_options_lib_dict_val) as ydl_lib_instance_obj_item:
                if (
                    ydl_lib_instance_obj_item.extract_info(params.youtube_url, download=True) is None
                ):  # pragma: no cover
                    self._log_warning("yt-dlp extract_info returned None for %s", params.actual_video_id)

            expected_lib_file_path_obj: Path = (
                params.temp_dir_path / f"{params.actual_video_id}.{target.lang_code}.{params.preferred_format}"
            )
            if expected_lib_file_path_obj.is_file() and expected_lib_file_path_obj.stat().st_size > 0:
                return expected_lib_file_path_obj

            alt_lib_file_path_obj: Path = params.temp_dir_path / f"{params.actual_video_id}.{params.preferred_format}"
            if alt_lib_file_path_obj.is_file() and alt_lib_file_path_obj.stat().st_size > 0:  # pragma: no cover
                self._log_info("Found lib subs with alt name: %s", alt_lib_file_path_obj)
                return alt_lib_file_path_obj
            self._log_warning(
                "File %s (or alt) not found/empty after lib call for %s, %s.",  # pragma: no cover
                expected_lib_file_path_obj.name,
                target.lang_code,
                target.type.value,
            )
            return None
        except (YtdlpDownloadError, YtdlpExtractorError, YtdlpUnavailableVideoError) as e_yt_dl_err_lib_item:  # type: ignore[misc]
            self._logger.warning(
                "yt-dlp lib download failed for lang '%s', type '%s': %s.",
                target.lang_code,
                target.type.value,
                str(e_yt_dl_err_lib_item),
            )
        except RuntimeError as e_runtime_lib_err_item:  # pragma: no cover
            self._logger.warning(
                "Runtime error yt-dlp lib for lang '%s', type '%s': %s.",
                target.lang_code,
                target.type.value,
                str(e_runtime_lib_err_item),
            )
        except ValueError as e_value_lib_err_item:  # pragma: no cover
            self._logger.warning(
                "ValueError yt-dlp lib for lang '%s', type '%s': %s.",
                target.lang_code,
                target.type.value,
                str(e_value_lib_err_item),
                exc_info=True,
            )
        return None

    def _attempt_single_transcript_download(
        self,
        video_info: VideoAndFormatInfo,
        target: SubtitleAttemptTarget,
        shared_ctx_ref: SLSharedContext,
        llm_cfg: LlmConfigDict,
        cache_cfg: CacheConfigDict,
    ) -> Optional[DownloadedSubtitleInfo]:
        """Attempt to download, parse, and LLM-deduplicate a single transcript.

        Tries downloading via yt-dlp library first, then falls back to CLI.
        The downloaded VTT content is then parsed and deduplicated using an LLM.

        Args:
            video_info: Contains URL, video ID, and preferred format.
            target: Specifies the language and type of subtitle.
            shared_ctx_ref: Reference to shared context for video title.
            llm_cfg: LLM configuration for deduplication.
            cache_cfg: Cache configuration for deduplication.

        Returns:
            Object with text, lang, and type if successful.
        """
        final_transcript_file_path_val: Optional[Path] = None
        download_method_used_val: str = "Unknown"
        with tempfile.TemporaryDirectory() as tmp_dir_path_str_item:
            tmp_dir_path_obj_item: Path = Path(tmp_dir_path_str_item)
            lib_dl_params_obj_item: LibraryDownloadParams = LibraryDownloadParams(
                video_info.youtube_url, video_info.actual_video_id, video_info.preferred_format, tmp_dir_path_obj_item
            )
            final_transcript_file_path_val = self._attempt_library_download(lib_dl_params_obj_item, target)

            if final_transcript_file_path_val:
                download_method_used_val = "Python Library"
            else:
                self._log_info("Lib download failed for %s, %s. CLI fallback.", target.lang_code, target.type.value)
                cli_dl_params_obj_item: CliDownloadParams = CliDownloadParams(
                    video_info.youtube_url,
                    video_info.actual_video_id,
                    video_info.preferred_format,
                    tmp_dir_path_obj_item,
                )
                cli_success_bool_val, cli_file_path_item = self._download_subtitles_via_cli(
                    cli_dl_params_obj_item, target
                )
                if cli_success_bool_val and cli_file_path_item:
                    final_transcript_file_path_val = cli_file_path_item
                    download_method_used_val = "CLI Fallback"
                else:
                    return None  # pragma: no cover

            if (
                final_transcript_file_path_val
                and final_transcript_file_path_val.is_file()
                and final_transcript_file_path_val.stat().st_size > 0
            ):
                self._log_info(
                    "Found %s subs file: %s (source: %s)",
                    target.type.value,
                    final_transcript_file_path_val,
                    download_method_used_val,
                )
                try:
                    current_video_title_str_val_item: str = cast(
                        str, shared_ctx_ref.get("current_youtube_video_title", "Unknown Video Title")
                    )
                    vtt_parse_context_obj_item: VttParseContext = VttParseContext(
                        current_video_title_str_val_item, target.lang_code, video_info.youtube_url, llm_cfg, cache_cfg
                    )
                    text_content_output_str_val: str = self._parse_vtt_to_plain_text(
                        final_transcript_file_path_val.read_text(encoding="utf-8"), vtt_parse_context_obj_item
                    )
                    self._log_info(
                        "Extracted & LLM-deduplicated text for %s subs for '%s' (lang: %s)",
                        target.type.value,
                        video_info.actual_video_id,
                        target.lang_code,
                    )
                    return DownloadedSubtitleInfo(
                        text=text_content_output_str_val, lang_code=target.lang_code, type=target.type
                    )
                except OSError as e_os_read_err_item:  # pragma: no cover
                    self._log_error("Failed to read %s: %s", final_transcript_file_path_val, e_os_read_err_item)
            else:  # pragma: no cover
                self._log_warning(
                    "File %s (from %s) not found/empty for %s, %s.",
                    final_transcript_file_path_val,
                    download_method_used_val,
                    target.lang_code,
                    target.type.value,
                )
        return None

    def _process_video_subtitles(
        self,
        youtube_url: str,
        metadata: VideoMetadata,
        prep_inputs: FetchYouTubeContentPreparedInputsYtdlp,
        llm_config: LlmConfigDict,
        cache_config: CacheConfigDict,
    ) -> Optional[DownloadedSubtitleInfo]:
        """Iterate preferred languages/types to download the best available subtitle.

        Constructs an attempt order and tries to download/process subtitles until one is successful.

        Args:
            youtube_url: The URL of the YouTube video.
            metadata: Extracted video metadata including available subtitle languages.
            prep_inputs: Prepared inputs from `pre_execution`.
            llm_config: LLM configuration for deduplication.
            cache_config: Cache configuration for deduplication.

        Returns:
            Information about the successfully downloaded and
            processed subtitle, or None if all attempts fail.
        """
        lang_preferences_list_val: list[str] = prep_inputs["expected_transcript_languages_on_yt"]
        prefer_manual_bool_val: bool = prep_inputs["prefer_manual_over_auto"]
        fallback_auto_bool_val: bool = prep_inputs["fallback_to_auto_captions"]
        preferred_format_str_item: str = prep_inputs["preferred_subtitle_download_format"]
        shared_context_obj_item: SLSharedContext = prep_inputs["shared_context_ref"]

        attempt_targets_list_obj_val: list[SubtitleAttemptTarget] = self._build_subtitle_attempt_order(
            metadata,
            lang_preferences_list_val,
            prefer_manual=prefer_manual_bool_val,  # Corrected keyword argument
            fallback_auto=fallback_auto_bool_val,  # Corrected keyword argument
        )
        if not attempt_targets_list_obj_val:
            self._log_warning("No subtitle attempts generated for video %s.", metadata.id)
            return None

        video_info_data_item = VideoAndFormatInfo(youtube_url, metadata.id, preferred_format_str_item)
        for attempt_target_val_item in attempt_targets_list_obj_val:
            self._log_info(
                "Next attempt: lang='%s', type='%s'",
                attempt_target_val_item.lang_code,
                attempt_target_val_item.type.value,
            )
            downloaded_info_val_obj_item: Optional[DownloadedSubtitleInfo] = self._attempt_single_transcript_download(
                video_info_data_item, attempt_target_val_item, shared_context_obj_item, llm_config, cache_config
            )
            if downloaded_info_val_obj_item and downloaded_info_val_obj_item.text.strip():
                return downloaded_info_val_obj_item
        self._log_warning("No suitable subtitles found for video %s after all attempts.", metadata.id)
        return None

    def _download_and_save_audio(  # pragma: no cover
        self, youtube_url: str, video_id: str, sanitized_title: str, run_specific_dir: Path
    ) -> Optional[str]:
        """Download audio track as MP3 using yt-dlp.

        Args:
            youtube_url: The URL of the YouTube video.
            video_id: The ID of the video.
            sanitized_title: Sanitized video title for the MP3 filename.
            run_specific_dir: Base output directory for the current run.

        Returns:
            Absolute path to the saved MP3 file if successful, else None.
        """
        self._log_info("Attempting audio download for video ID: %s", video_id)
        audio_output_path_val_obj: Path = run_specific_dir / AUDIO_SUBDIR_NAME
        try:
            audio_output_path_val_obj.mkdir(parents=True, exist_ok=True)
        except OSError as e_mkdir_err_audio:
            self._log_error("Failed to create audio dir %s: %s", audio_output_path_val_obj, e_mkdir_err_audio)
            return None

        final_path_template_audio_str: str = str(audio_output_path_val_obj / f"{sanitized_title}.%(ext)s")
        final_mp3_path_obj_item: Path = audio_output_path_val_obj / f"{sanitized_title}.mp3"
        ydl_audio_opts_data_dict: YdlOpts = {
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            "outtmpl": final_path_template_audio_str,
            "skip_download": False,
            "noplaylist": True,
            "logger": self._yt_dlp_custom_logger,
            "quiet": False,
            "no_warnings": False,
            "verbose": True,
            "restrictfilenames": True,
            "writesubtitles": False,
            "writeautomaticsubs": False,
        }
        try:  # Library attempt for audio
            assert yt_dlp_module is not None
            with yt_dlp_module.YoutubeDL(ydl_audio_opts_data_dict) as ydl_audio_instance_obj_item:
                ydl_audio_instance_obj_item.download([youtube_url])
            if final_mp3_path_obj_item.is_file() and final_mp3_path_obj_item.stat().st_size > 0:
                self._log_info("Audio downloaded to: %s (via library)", final_mp3_path_obj_item)
                return str(final_mp3_path_obj_item.resolve())
            self._log_warning("Audio library download did not result in expected MP3: %s", final_mp3_path_obj_item)
        except (
            YtdlpDownloadError,
            YtdlpExtractorError,
            YtdlpUnavailableVideoError,
            RuntimeError,  # type: ignore[misc]
            AttributeError,
            OSError,
            ValueError,
        ) as e_lib_audio_err_item:
            self._log_warning(
                "Audio library download failed for %s: %s. Trying CLI fallback.", video_id, e_lib_audio_err_item
            )

        audio_cli_cmd_list_items: list[str] = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "192K",
            "--output",
            final_path_template_audio_str,
            "--no-warnings",
            youtube_url,
        ]
        self._log_info("Executing yt-dlp CLI for audio (fallback): %s", " ".join(audio_cli_cmd_list_items))
        cli_creation_flags_val_item: int = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        try:
            audio_process_cli_obj: subprocess.Popen[str] = subprocess.Popen(
                audio_cli_cmd_list_items,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=cli_creation_flags_val_item,
            )
            self._handle_cli_process_output(audio_process_cli_obj)
            if (
                audio_process_cli_obj.returncode == 0
                and final_mp3_path_obj_item.is_file()
                and final_mp3_path_obj_item.stat().st_size > 0
            ):
                self._log_info("Audio downloaded to: %s (via CLI)", final_mp3_path_obj_item)
                return str(final_mp3_path_obj_item.resolve())
            self._log_error("Audio CLI download failed or MP3 not found. Code: %s", audio_process_cli_obj.returncode)
        except (FileNotFoundError, subprocess.SubprocessError, OSError, ValueError) as e_cli_audio_err_item:
            self._log_error("Error exec yt-dlp CLI for audio: %s", e_cli_audio_err_item, exc_info=True)
        return None

    def _conditionally_download_audio_wrapper(
        self,
        youtube_url_str_arg: str,
        video_id_str_arg: str,
        sanitized_title_str_arg: str,
        run_specific_dir_path: Path,
        *,
        cli_extract_audio_flag_param: bool,
    ) -> Optional[str]:
        """Wrap logic to conditionally trigger audio download based on internal and CLI flags.

        Args:
            youtube_url_str_arg: The URL of the YouTube video.
            video_id_str_arg: The ID of the video.
            sanitized_title_str_arg: Sanitized video title for filename.
            run_specific_dir_path: Base output directory for the current run.
            cli_extract_audio_flag_param: Boolean flag from CLI indicating if audio
                                          extraction was requested.

        Returns:
            Path to downloaded audio file if successful, or None.
        """
        should_download_audio_bool_val: bool = (
            self._DOWNLOAD_AUDIO_MP3_SECRET_FEATURE_ENABLED or cli_extract_audio_flag_param
        )
        if not should_download_audio_bool_val:
            self._log_info("Audio download skipped (neither secret feature constant nor CLI flag enabled).")
            return None

        if not self._DOWNLOAD_AUDIO_MP3_SECRET_FEATURE_ENABLED and cli_extract_audio_flag_param:
            self._log_info("Audio download triggered by CLI --extract-audio flag (secret constant is False).")
        elif self._DOWNLOAD_AUDIO_MP3_SECRET_FEATURE_ENABLED:  # pragma: no cover
            self._log_info("Audio download triggered by _DOWNLOAD_AUDIO_MP3_SECRET_FEATURE_ENABLED=True constant.")

        return self._download_and_save_audio(
            youtube_url_str_arg, video_id_str_arg, sanitized_title_str_arg, run_specific_dir_path
        )

    def execution(
        self, prepared_inputs: FetchYouTubeContentPreparedInputsYtdlp
    ) -> FetchYouTubeContentExecutionResultYtdlp:
        """Execute fetching of YouTube transcript and metadata using yt-dlp.

        Orchestrates metadata fetching, subtitle selection, download, parsing
        (including LLM deduplication), and optional audio download.

        Args:
            prepared_inputs: A dictionary from `pre_execution` containing video ID,
                URL, output directories, language preferences, and LLM/cache configs.

        Returns:
            A dictionary with extracted video info and transcript, or None on critical failure.
            Keys include: "video_id", "video_title", "youtube_url", "video_description",
            "upload_date", "view_count", "uploader", "original_transcript_text",
            "original_lang_code", and "downloaded_audio_path".

        Raises:
            LlmApiError: If unrecoverable errors occur during yt-dlp or LLM interactions.
        """
        if prepared_inputs.get("skip") or not YTDLP_AVAILABLE:  # pragma: no cover
            reason_skip_val: str = str(prepared_inputs.get("reason", "yt-dlp not available"))
            self._log_info(f"Skipping YouTube content execution. Reason: {reason_skip_val}")
            return None

        video_id_initial_str_val: str = prepared_inputs["video_id"]
        youtube_url_str_val_item: str = prepared_inputs["youtube_url"]
        run_dir_path_obj_val: Path = prepared_inputs["run_specific_output_dir"]
        shared_ctx_obj_val: SLSharedContext = prepared_inputs["shared_context_ref"]
        llm_cfg_obj: LlmConfigDict = cast(LlmConfigDict, prepared_inputs.get("llm_config", {}))
        cache_cfg_obj: CacheConfigDict = cast(CacheConfigDict, prepared_inputs.get("cache_config", {}))
        cli_audio_flag_val_bool: bool = cast(bool, shared_ctx_obj_val.get("cli_extract_audio_enabled", False))

        self._log_info("Executing YouTube processing for video ID: %s", video_id_initial_str_val)
        if cli_audio_flag_val_bool:
            self._log_info("CLI flag --extract-audio is set. Audio download will be attempted.")

        try:
            video_metadata_obj_val: Optional[VideoMetadata] = self._get_video_metadata_with_yt_dlp(
                youtube_url_str_val_item, video_id_initial_str_val, shared_ctx_obj_val
            )
            if not video_metadata_obj_val:
                fallback_title_str_val: str = cast(
                    str,
                    prepared_inputs.get(
                        "video_title_from_context", f"YT Video (meta fail): {video_id_initial_str_val}"
                    ),
                )
                self._log_error(
                    "Failed metadata for video %s. Title: %s", video_id_initial_str_val, fallback_title_str_val
                )
                return {
                    "video_id": video_id_initial_str_val,
                    "video_title": fallback_title_str_val,
                    "youtube_url": youtube_url_str_val_item,
                }

            final_video_id_str_val: str = video_metadata_obj_val.id
            final_video_title_str_val: str = video_metadata_obj_val.title
            final_sanitized_title_str_val: str = cast(
                str,
                shared_ctx_obj_val.get("current_youtube_sanitized_title", sanitize_filename(final_video_title_str_val)),
            )

            audio_path_str_val: Optional[str] = self._conditionally_download_audio_wrapper(
                youtube_url_str_val_item,
                final_video_id_str_val,
                final_sanitized_title_str_val,
                run_dir_path_obj_val,
                cli_extract_audio_flag_param=cli_audio_flag_val_bool,
            )
            sub_info_obj_val: Optional[DownloadedSubtitleInfo] = self._process_video_subtitles(
                youtube_url_str_val_item, video_metadata_obj_val, prepared_inputs, llm_cfg_obj, cache_cfg_obj
            )
            result_data_dict_val: dict[str, Any] = {
                "video_id": final_video_id_str_val,
                "video_title": final_video_title_str_val,
                "youtube_url": youtube_url_str_val_item,
                "video_description": video_metadata_obj_val.description,
                "upload_date": video_metadata_obj_val.upload_date,
                "view_count": video_metadata_obj_val.view_count,
                "uploader": video_metadata_obj_val.uploader,
                "downloaded_audio_path": audio_path_str_val,
            }
            if sub_info_obj_val:
                result_data_dict_val["original_transcript_text"] = sub_info_obj_val.text
                result_data_dict_val["original_lang_code"] = sub_info_obj_val.lang_code
            return result_data_dict_val
        except (YtdlpDownloadError, YtdlpExtractorError, YtdlpUnavailableVideoError) as e_yt_dlp_main:  # type: ignore[misc] # pragma: no cover
            self._log_error("yt-dlp error for video %s: %s", video_id_initial_str_val, e_yt_dlp_main)
            raise LlmApiError(f"yt-dlp error: {e_yt_dlp_main!s}", provider="yt-dlp") from e_yt_dlp_main
        except RuntimeError as e_runtime_main_exec:  # pragma: no cover
            self._log_error(
                "Runtime error for video %s: %s", video_id_initial_str_val, e_runtime_main_exec, exc_info=True
            )
            raise LlmApiError(
                f"Runtime error (yt-dlp): {e_runtime_main_exec!s}", provider="yt-dlp"
            ) from e_runtime_main_exec
        except ValueError as e_value_main_exec:  # pragma: no cover
            self._log_error("ValueError for video %s: %s", video_id_initial_str_val, e_value_main_exec, exc_info=True)
            raise LlmApiError(f"Value error (yt-dlp): {e_value_main_exec!s}", provider="yt-dlp") from e_value_main_exec

    def execution_fallback(
        self, prepared_inputs: FetchYouTubeContentPreparedInputsYtdlp, exc: Exception
    ) -> FetchYouTubeContentExecutionResultYtdlp:
        """Handle fallback if all `execution` attempts for yt-dlp fail.

        This method is invoked by the `BaseNode`'s retry mechanism if all attempts
        of the `execution` method raise a recoverable error.

        Args:
            prepared_inputs: The dictionary of inputs
                that was passed to the `execution` method.
            exc: The exception object from the last failed execution attempt.

        Returns:
            A dictionary containing basic video
            information (ID, title, URL) and an indication of the processing error.
            `downloaded_audio_path` is set to None.
        """
        vid_id_fb_val_str: str = str(prepared_inputs.get("video_id", "Unknown"))
        url_fb_val_str: Optional[str] = cast(Optional[str], prepared_inputs.get("youtube_url"))
        title_fb_val_str: str = f"YouTube Video (processing error): {vid_id_fb_val_str}"
        self._log_error(
            "All yt-dlp processing attempts for video ID '%s' failed. Last error: %s",
            vid_id_fb_val_str,
            exc,
            exc_info=(exc is not None),
        )
        return {
            "video_id": vid_id_fb_val_str,
            "video_title": title_fb_val_str,
            "youtube_url": url_fb_val_str,
            "downloaded_audio_path": None,
        }

    def _get_transcripts_output_dir(self, run_specific_output_dir: Path) -> Path:
        """Determine and return the path to the 'transcripts' subdirectory.

        Args:
            run_specific_output_dir: The main output directory for the current run.

        Returns:
            The `Path` object for the 'transcripts' subdirectory.
        """
        return run_specific_output_dir / TRANSCRIPTS_SUBDIR_NAME

    def _save_standalone_transcript_file_yt(self, save_data: StandaloneTranscriptSaveData) -> Optional[str]:
        """Save the standalone transcript (original or translated) to a file.

        The method constructs the filename based on video title, language, and type (orig/final).
        It ensures the target directory exists and writes the content. A Markdown header
        is added to the content if it's a translated version or if the original content
        doesn't appear to have one already.

        Args:
            save_data: A dataclass object containing all necessary
                information for saving the transcript file, including the output directory,
                video details, language, text content, and format.

        Returns:
            The absolute path to the saved file as a string if successful,
            otherwise None.
        """
        try:
            save_data.transcripts_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e_dir_create_err_val:  # pragma: no cover
            self._log_error(
                "Failed to create transcript directory %s: %s", save_data.transcripts_output_dir, e_dir_create_err_val
            )
            return None

        filename_suffix_str_val: str = "final" if save_data.is_translated else "orig"
        sanitized_title_str_item: str = save_data.sanitized_video_title or f"video_{save_data.video_id}"
        filename_base_str_item: str = (
            f"ts_{sanitized_title_str_item}_{save_data.original_lang}_{filename_suffix_str_val}"
        )
        final_filename_str_item: str = f"{filename_base_str_item}.{save_data.output_format}"
        final_filepath_obj_item: Path = save_data.transcripts_output_dir / final_filename_str_item

        text_to_process_str_val: str = save_data.original_text or ""
        output_content_parts_list_item: list[str] = []

        header_already_present_bool_item: bool = text_to_process_str_val.strip().startswith(
            f"# Transcript: {save_data.video_title}"
        )

        if save_data.is_translated or not header_already_present_bool_item:
            output_content_parts_list_item.append(f"# Transcript: {save_data.video_title}")
            header_info_line_str_val: str = f"(Language: {save_data.original_lang}"
            if save_data.youtube_url:
                header_info_line_str_val += f" , Source: {save_data.youtube_url}"
            if save_data.is_translated:
                header_info_line_str_val += " , Translated"
            header_info_line_str_val += " )"
            output_content_parts_list_item.extend([header_info_line_str_val, "", text_to_process_str_val.strip()])
        else:
            output_content_parts_list_item.append(text_to_process_str_val.strip())

        final_text_to_write_str: str = "\n".join(output_content_parts_list_item)
        try:
            final_filepath_obj_item.write_text(final_text_to_write_str, encoding="utf-8")
            self._log_info("Saved transcript to: %s", final_filepath_obj_item.resolve())
            return str(final_filepath_obj_item.resolve())
        except OSError as e_file_write_err_val:  # pragma: no cover
            self._log_error("Failed to write transcript file %s: %s", final_filepath_obj_item, e_file_write_err_val)
            return None

    def _add_description_to_pipeline_files_yt(
        self, shared_context: SLSharedContext, video_title: str, description: str
    ) -> None:
        """Add the video description as a Markdown file to `shared_context["files"]`.

        This content is intended for further LLM processing in "llm_extended" mode.

        Args:
            shared_context: The shared context dictionary.
            video_title: The title of the YouTube video.
            description: The description text of the video.
        """
        md_content_str_item: str = f"# Video Description: {video_title}\n\n{description}"
        files_list_any_item: Any = shared_context.get("files", [])
        if not isinstance(files_list_any_item, list):  # pragma: no cover
            self._log_warning("shared_context['files'] is not a list. Initializing as empty list.")
            files_list_any_item = []

        current_files_list_obj: "FilePathContentList" = cast("FilePathContentList", files_list_any_item)
        current_files_list_obj.append((DESCRIPTION_FILE_FOR_PIPELINE, md_content_str_item))
        shared_context["files"] = current_files_list_obj
        self._log_info(
            "Added YouTube video description for '%s' to shared_context['files'] as '%s'.",
            video_title,
            DESCRIPTION_FILE_FOR_PIPELINE,
        )

    def _update_shared_context_yt(
        self, shared_context: SLSharedContext, context_info: YouTubeContextUpdateInfo
    ) -> None:
        """Update various YouTube-related keys in the `shared_context` dictionary.

        This method centralizes the update of shared context variables related to
        the YouTube video processing, ensuring consistency.

        Args:
            shared_context: The shared context dictionary to update.
            context_info: A dataclass object containing all the
                information to be set in the shared context.
        """
        shared_context.update(
            {
                "youtube_processed_successfully": context_info.processed_successfully,
                "current_youtube_video_id": context_info.video_id,
                "current_youtube_original_lang": context_info.original_lang,
                "current_youtube_standalone_transcript_path": context_info.standalone_transcript_path,
                "current_youtube_video_title": context_info.video_title,
                "current_youtube_url": context_info.youtube_url,
                "current_youtube_description": context_info.video_description,
                "current_youtube_upload_date": context_info.upload_date,
                "current_youtube_view_count": context_info.view_count,
                "current_youtube_original_transcript_text": context_info.original_transcript_text,
                "current_youtube_uploader": context_info.uploader,
                "current_youtube_audio_path": context_info.downloaded_audio_path,
            }
        )
        shared_context.setdefault("current_youtube_final_transcript_lang", None)
        shared_context.setdefault("current_youtube_final_transcript_path", None)
        final_sanitized_title_str_val_item: str = sanitize_filename(context_info.video_title or "unknown_video")
        shared_context["current_youtube_sanitized_title"] = final_sanitized_title_str_val_item
        if context_info.run_specific_output_dir:
            shared_context["final_output_dir_web_crawl"] = str(context_info.run_specific_output_dir)
        status_msg_str_val: str = "complete" if context_info.processed_successfully else "finished with issues"
        self._log_info(
            "YouTube content post_execution %s for video ID: %s", status_msg_str_val, context_info.video_id or "N/A"
        )

    def _extract_data_for_context_payload(
        self,
        execution_outputs: FetchYouTubeContentExecutionResultYtdlp,
        prepared_inputs: FetchYouTubeContentPreparedInputsYtdlp,
        shared_context: SLSharedContext,
    ) -> tuple[Optional[str], Optional[str]]:
        """Extract final video ID and title for creating the context update payload.

        Prioritizes values already set in `shared_context` (e.g., by metadata fetch),
        then from `execution_outputs`, and finally from `prepared_inputs` as fallback.

        Args:
            execution_outputs: The result from the `execution` phase.
            prepared_inputs: The inputs prepared by `pre_execution`.
            shared_context: The current shared context.

        Returns:
            A tuple containing the final video ID and video title.
        """
        exec_outputs_safe_dict_item: dict[str, Any] = execution_outputs or {}
        final_video_id_str_item: Optional[str] = cast(
            Optional[str],
            shared_context.get(
                "current_youtube_video_id", exec_outputs_safe_dict_item.get("video_id", prepared_inputs.get("video_id"))
            ),
        )
        final_video_title_str_item: Optional[str] = cast(
            Optional[str],
            shared_context.get(
                "current_youtube_video_title",
                exec_outputs_safe_dict_item.get("video_title", prepared_inputs.get("video_title_from_context")),
            ),
        )
        return final_video_id_str_item, final_video_title_str_item

    def _create_initial_context_payload(
        self,
        prepared_inputs: FetchYouTubeContentPreparedInputsYtdlp,
        execution_outputs: FetchYouTubeContentExecutionResultYtdlp,
        final_video_id: Optional[str],
        final_video_title: Optional[str],
    ) -> YouTubeContextUpdateInfo:
        """Create the initial `YouTubeContextUpdateInfo` object for `post_execution`.

        Populates the dataclass with data primarily from `execution_outputs` and fallbacks
        from `prepared_inputs` or defaults. `processed_successfully` is initially False.

        Args:
            prepared_inputs: Inputs from `pre_execution`.
            execution_outputs: Results from `execution`.
            final_video_id: The resolved video ID.
            final_video_title: The resolved video title.

        Returns:
            An initialized dataclass instance.
        """
        exec_outputs_safe_dict_item_val: dict[str, Any] = execution_outputs or {}
        return YouTubeContextUpdateInfo(
            processed_successfully=False,
            video_id=final_video_id,
            video_title=final_video_title,
            original_lang=cast(Optional[str], exec_outputs_safe_dict_item_val.get("original_lang_code")),
            original_transcript_text=cast(
                Optional[str], exec_outputs_safe_dict_item_val.get("original_transcript_text")
            ),
            standalone_transcript_path=None,
            run_specific_output_dir=prepared_inputs["run_specific_output_dir"],
            youtube_url=cast(Optional[str], prepared_inputs.get("youtube_url")),
            video_description=cast(Optional[str], exec_outputs_safe_dict_item_val.get("video_description")),
            upload_date=cast(Optional[str], exec_outputs_safe_dict_item_val.get("upload_date")),
            view_count=cast(Optional[int], exec_outputs_safe_dict_item_val.get("view_count")),
            uploader=cast(Optional[str], exec_outputs_safe_dict_item_val.get("uploader")),
            downloaded_audio_path=cast(Optional[str], exec_outputs_safe_dict_item_val.get("downloaded_audio_path")),
        )

    def _log_missing_transcript_info_error(  # pragma: no cover
        self,
        context_payload_obj_val: YouTubeContextUpdateInfo,
        final_sanitized_title_str_val: str,
        original_text_str_val: Optional[str],
    ) -> None:
        """Log an error message if critical information for saving a transcript is missing.

        Args:
            context_payload_obj_val: The context payload being processed.
            final_sanitized_title_str_val: The sanitized title for the video.
            original_text_str_val: The original transcript text.
        """
        missing_items_list_str: list[str] = [
            p_name_str_item
            for p_name_str_item, val_item_obj_item in [
                ("text", original_text_str_val),
                ("lang", context_payload_obj_val.original_lang),
                ("id", context_payload_obj_val.video_id),
                ("title", context_payload_obj_val.video_title),
                (
                    "san_title",
                    final_sanitized_title_str_val if final_sanitized_title_str_val != "unknown_video" else None,
                ),
            ]
            if not val_item_obj_item
        ]
        self._log_error(
            "Critical info missing for video %s. Missing: %s. Cannot save original transcript.",
            context_payload_obj_val.video_id or "N/A",
            ", ".join(missing_items_list_str),
        )

    def _save_transcript_and_update_payload(
        self,
        context_payload_obj_item: YouTubeContextUpdateInfo,
        prepared_inputs_dict_item: FetchYouTubeContentPreparedInputsYtdlp,
        original_text_str_item: str,
        final_sanitized_title_str_item: str,
    ) -> None:
        """Save the standalone original transcript file and update the context payload.

        This method handles the file saving operation and updates the `context_payload_obj_item`
        with the path to the saved file and success status.

        Args:
            context_payload_obj_item: The context payload to update.
            prepared_inputs_dict_item: Prepared inputs containing output directory and format information.
            original_text_str_item: The original transcript text to save.
            final_sanitized_title_str_item: The sanitized title used for filename generation.
        """
        # Assertions ensure MyPy that these Optional[str] are indeed str at this point
        video_id_asserted: str = cast(str, context_payload_obj_item.video_id)
        video_title_asserted: str = cast(str, context_payload_obj_item.video_title)
        original_lang_asserted: str = cast(str, context_payload_obj_item.original_lang)
        run_dir_asserted: Path = cast(Path, prepared_inputs_dict_item["run_specific_output_dir"])

        transcripts_dir_path_obj_val: Path = self._get_transcripts_output_dir(run_dir_asserted)
        save_data_obj_item_val: StandaloneTranscriptSaveData = StandaloneTranscriptSaveData(
            transcripts_output_dir=transcripts_dir_path_obj_val,
            video_id=video_id_asserted,
            sanitized_video_title=final_sanitized_title_str_item,
            video_title=video_title_asserted,
            original_lang=original_lang_asserted,
            original_text=original_text_str_item,
            youtube_url=cast(Optional[str], prepared_inputs_dict_item.get("youtube_url")),
            output_format=str(prepared_inputs_dict_item["standalone_transcript_format"]),
            is_translated=False,
        )
        saved_file_path_str_val_item: Optional[str] = self._save_standalone_transcript_file_yt(save_data_obj_item_val)
        if saved_file_path_str_val_item:
            context_payload_obj_item.standalone_transcript_path = saved_file_path_str_val_item
            context_payload_obj_item.processed_successfully = True

    def _handle_llm_extended_mode_for_yt(
        self, shared_context_obj_val: SLSharedContext, context_payload_obj_val: YouTubeContextUpdateInfo
    ) -> None:
        """Add video description to shared_context["files"] if in "llm_extended" mode.

        This is done only if the primary YouTube processing (transcript fetching) was successful.

        Args:
            shared_context_obj_val: The shared context dictionary.
            context_payload_obj_val: The context payload containing video details.
        """
        config_dict_item: dict[str, Any] = cast(dict, shared_context_obj_val.get("config", {}))
        crawler_options_item_dict: dict[str, Any] = config_dict_item.get("FL02_web_crawling", {}).get(
            "crawler_options", {}
        )
        processing_mode_str_val_item: str = str(crawler_options_item_dict.get("processing_mode", "minimalistic"))

        if processing_mode_str_val_item == "llm_extended" and context_payload_obj_val.processed_successfully:
            if context_payload_obj_val.video_description and context_payload_obj_val.video_title:
                self._add_description_to_pipeline_files_yt(
                    shared_context_obj_val,
                    context_payload_obj_val.video_title,
                    context_payload_obj_val.video_description,
                )
        else:
            shared_context_obj_val.setdefault("files", [])
            if (
                processing_mode_str_val_item == "llm_extended" and not context_payload_obj_val.processed_successfully
            ):  # pragma: no cover
                self._log_warning(
                    "LLM_extended mode: Video description not added to pipeline files as "
                    "YouTube content processing was not fully successful."
                )

    def _process_and_save_transcript_wrapper(
        self,
        shared_context_obj_item: SLSharedContext,
        context_payload_obj_item: YouTubeContextUpdateInfo,
        prepared_inputs_obj_item: FetchYouTubeContentPreparedInputsYtdlp,
    ) -> None:
        """Wrap the logic for processing and saving the original transcript.

        Checks for necessary data, saves the transcript file, and handles
        updates to the context payload and shared context for "llm_extended" mode.

        Args:
            shared_context_obj_item: The main shared context.
            context_payload_obj_item: The payload containing transcript data.
            prepared_inputs_obj_item: Prepared inputs for the node.
        """
        original_transcript_str_val: Optional[str] = context_payload_obj_item.original_transcript_text
        final_sanitized_title_val_str: str = cast(
            str,
            shared_context_obj_item.get(
                "current_youtube_sanitized_title",
                sanitize_filename(context_payload_obj_item.video_title or "unknown_video"),
            ),
        )
        can_save_transcript_bool_val: bool = bool(
            original_transcript_str_val
            and context_payload_obj_item.original_lang
            and context_payload_obj_item.video_id
            and context_payload_obj_item.video_title
            and final_sanitized_title_val_str != "unknown_video"
        )

        if can_save_transcript_bool_val:
            assert original_transcript_str_val is not None  # For mypy, after bool check
            self._save_transcript_and_update_payload(
                context_payload_obj_item,
                prepared_inputs_obj_item,
                original_transcript_str_val,
                final_sanitized_title_val_str,
            )
            self._handle_llm_extended_mode_for_yt(shared_context_obj_item, context_payload_obj_item)
        else:  # pragma: no cover
            self._log_missing_transcript_info_error(
                context_payload_obj_item, final_sanitized_title_val_str, original_transcript_str_val
            )
            shared_context_obj_item.setdefault("files", [])  # Ensure 'files' exists

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: FetchYouTubeContentPreparedInputsYtdlp,
        execution_outputs: FetchYouTubeContentExecutionResultYtdlp,
    ) -> None:
        """Finalize YouTube content processing, save files, and update shared_context.

        This method takes the results from the `execution` phase (which includes
        video metadata and the LLM-deduplicated original transcript), orchestrates
        the saving of the original transcript file, and updates the `shared_context`
        with all relevant YouTube information for subsequent nodes.

        Args:
            shared_context: The shared context dictionary to be updated.
            prepared_inputs: The dictionary of inputs prepared by `pre_execution`.
            execution_outputs: The dictionary returned by `execution`, containing
                video metadata and transcript text, or None if execution failed.
        """
        final_video_id_val_str: Optional[str]
        final_video_title_val_str: Optional[str]
        final_video_id_val_str, final_video_title_val_str = self._extract_data_for_context_payload(
            execution_outputs, prepared_inputs, shared_context
        )
        context_update_payload_obj_val: YouTubeContextUpdateInfo = self._create_initial_context_payload(
            prepared_inputs, execution_outputs, final_video_id_val_str, final_video_title_val_str
        )
        if not execution_outputs:  # pragma: no cover
            self._log_error("FetchYouTubeContent post_execution: No outputs received from execution phase.")
            shared_context.setdefault("files", [])
        else:
            self._process_and_save_transcript_wrapper(shared_context, context_update_payload_obj_val, prepared_inputs)
        self._update_shared_context_yt(shared_context, context_info=context_update_payload_obj_val)


# End of src/FL02_web_crawling/nodes/n01c_youtube_content.py
