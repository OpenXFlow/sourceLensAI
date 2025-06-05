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

"""Node responsible for segmenting crawled web page content into smaller chunks."""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Generator, Optional, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.utils.helpers import sanitize_filename

if TYPE_CHECKING:
    from sourcelens.core.common_types import FilePathContentList, WebContentChunk


SegmentWebContentPreparedInputs: TypeAlias = list[tuple[str, str, dict[str, Any]]]
SegmentWebContentExecutionResult: TypeAlias = list["WebContentChunk"]

DEFAULT_MIN_CHUNK_CHAR_LENGTH: Final[int] = 150
DEFAULT_HEADING_LEVELS_TO_SPLIT_ON: Final[list[int]] = [1, 2, 3]
MAX_HEADING_LEVEL: Final[int] = 6

EXPECTED_FILE_DATA_ITEM_LENGTH_WEB_CHUNK: Final[int] = 2

module_logger_segment_web: logging.Logger = logging.getLogger(__name__)


class SegmentWebContent(BaseNode[SegmentWebContentPreparedInputs, SegmentWebContentExecutionResult]):
    """Segments web content (Markdown) into smaller chunks based on headings."""

    def _create_dynamic_regexes(self, heading_levels: list[int]) -> tuple[re.Pattern[str], re.Pattern[str]]:
        """Create dynamic regexes based on specified heading levels.

        Args:
            heading_levels (list[int]): A list of integer heading levels (e.g., [1, 2, 3])
                                        to use as split points for segmentation.

        Returns:
            tuple[re.Pattern[str], re.Pattern[str]]: A tuple containing two compiled regex patterns:
                                                     - The first pattern matches headings and their content.
                                                     - The second pattern matches initial content before any specified heading.
        """  # noqa: E501
        levels_to_use: list[int]
        if not heading_levels:
            levels_to_use = DEFAULT_HEADING_LEVELS_TO_SPLIT_ON
        else:
            levels_to_use = sorted(set(h_level for h_level in heading_levels if 1 <= h_level <= MAX_HEADING_LEVEL))
            if not levels_to_use:
                levels_to_use = DEFAULT_HEADING_LEVELS_TO_SPLIT_ON

        levels_str: str = "".join(map(str, levels_to_use))
        heading_regex_str: str = rf"(^#{{{levels_str}}})\s+([^\n]+)\n(.*?)(?=(^#{{{levels_str}}}\s+[^\n]+$)|\Z)"
        initial_content_regex_str: str = rf"^(.*?)(?=(^#{{{levels_str}}}\s+[^\n]+$)|\Z)"

        return (
            re.compile(heading_regex_str, re.MULTILINE | re.DOTALL),
            re.compile(initial_content_regex_str, re.MULTILINE | re.DOTALL),
        )

    def _yield_initial_or_full_content_chunk(
        self, filepath: str, content: str, min_chunk_len: int, initial_content_regex: re.Pattern[str]
    ) -> tuple[Optional["WebContentChunk"], int]:
        """Yield a chunk for initial content or full content if no headings found.

        Args:
            filepath (str): The path of the source file.
            content (str): The full content of the source file.
            min_chunk_len (int): Minimum character length for a chunk to be considered.
            initial_content_regex (re.Pattern[str]): Regex to find initial content.

        Returns:
            tuple[Optional["WebContentChunk"], int]: A tuple containing the generated WebContentChunk
                                                   (or None if no valid chunk is found) and the
                                                   position in content after this chunk.
        """
        current_file_stem: str = sanitize_filename(Path(filepath).stem)
        match: Optional[re.Match[str]] = initial_content_regex.match(content)
        chunk_to_yield: Optional["WebContentChunk"] = None
        last_pos: int = 0

        if match:
            initial_text: str = match.group(1).strip()
            if initial_text and len(initial_text) >= min_chunk_len:
                chunk_id: str = f"{current_file_stem}_initial_content_0"
                self._log_debug(
                    "Yielding initial_content chunk: ID='%s', Title='Initial Content', Length=%d",
                    chunk_id,
                    len(initial_text),
                )
                chunk_to_yield = cast(
                    "WebContentChunk",
                    {
                        "chunk_id": chunk_id,
                        "source_filepath": filepath,
                        "title": "Initial Content",
                        "content": initial_text,
                        "char_count": len(initial_text),
                    },
                )
            elif initial_text:
                self._log_debug(
                    "Skipping initial_content for '%s': len %d < min %d", filepath, len(initial_text), min_chunk_len
                )

            last_pos = match.end(1) if initial_text else 0
            is_full_content_match: bool = match.group(2) is None and match.end() == len(content)
            if chunk_to_yield is None and is_full_content_match and len(content.strip()) >= min_chunk_len:
                chunk_id_full: str = f"{current_file_stem}_full_content_0"
                self._log_debug(
                    "Yielding full_content chunk (no specified headings found): ID='%s', Title='%s', Length=%d",
                    chunk_id_full,
                    Path(filepath).name,
                    len(content.strip()),
                )
                chunk_to_yield = cast(
                    "WebContentChunk",
                    {
                        "chunk_id": chunk_id_full,
                        "source_filepath": filepath,
                        "title": Path(filepath).name,
                        "content": content.strip(),
                        "char_count": len(content.strip()),
                    },
                )
                last_pos = len(content)
        return chunk_to_yield, last_pos

    def _yield_section_chunks(
        self, filepath: str, content: str, min_chunk_len: int, heading_regex: re.Pattern[str], start_offset: int
    ) -> tuple[list["WebContentChunk"], int]:
        """Yield chunks for sections found by heading_regex, starting from an offset.

        Args:
            filepath (str): The path of the source file.
            content (str): The full content of the source file.
            min_chunk_len (int): Minimum character length for a chunk.
            heading_regex (re.Pattern[str]): Regex to find sections based on headings.
            start_offset (int): The character offset in content from which to start searching.

        Returns:
            tuple[list["WebContentChunk"], int]: A tuple containing a list of generated WebContentChunks
                                                 and the position in content after the last processed chunk.
        """
        current_file_stem: str = sanitize_filename(Path(filepath).stem)
        chunks: list["WebContentChunk"] = []
        last_pos_processed: int = start_offset
        chunk_index_offset: int = 1 if start_offset > 0 else 0

        for match in heading_regex.finditer(content, pos=start_offset):
            heading_level_str: str = match.group(1)
            heading_text: str = match.group(2).strip()
            section_content_text: str = match.group(3).strip()

            if section_content_text and len(section_content_text) >= min_chunk_len:
                chunk_id_base: str = (
                    sanitize_filename(heading_text, max_len=40) or f"section_{chunk_index_offset + len(chunks)}"
                )
                chunk_id: str = f"{current_file_stem}_{chunk_id_base}"
                self._log_debug(
                    "Yielding section chunk: ID='%s', Title='%s', Level=%d, Length=%d",
                    chunk_id,
                    heading_text,
                    len(heading_level_str),
                    len(section_content_text),
                )
                chunks.append(
                    cast(
                        "WebContentChunk",
                        {
                            "chunk_id": chunk_id,
                            "source_filepath": filepath,
                            "title": heading_text,
                            "content": section_content_text,
                            "char_count": len(section_content_text),
                            "heading_level": len(heading_level_str),
                        },
                    )
                )
            elif section_content_text:
                self._log_debug(
                    "Skipping section '%s' in '%s': content len %d < min %d",
                    heading_text,
                    filepath,
                    len(section_content_text),
                    min_chunk_len,
                )
            last_pos_processed = match.end()
        return chunks, last_pos_processed

    def _yield_final_content_chunk(
        self, filepath: str, content: str, min_chunk_len: int, last_pos_processed: int, num_existing_chunks: int
    ) -> Optional["WebContentChunk"]:
        """Yield a chunk for content after the last recognized heading, if significant.

        Args:
            filepath (str): The path of the source file.
            content (str): The full content of the source file.
            min_chunk_len (int): Minimum character length for a chunk.
            last_pos_processed (int): The character offset in content after the last processed section.
            num_existing_chunks (int): The number of chunks already generated for this file.

        Returns:
            Optional["WebContentChunk"]: A WebContentChunk if valid final content is found, else None.
        """
        current_file_stem: str = sanitize_filename(Path(filepath).stem)
        remaining_content: str = content[last_pos_processed:].strip()
        if remaining_content and len(remaining_content) >= min_chunk_len:
            chunk_id: str = f"{current_file_stem}_final_content_{num_existing_chunks}"
            self._log_debug(
                "Yielding final_content chunk: ID='%s', Title='Final Content Section', Length=%d",
                chunk_id,
                len(remaining_content),
            )
            return cast(
                "WebContentChunk",
                {
                    "chunk_id": chunk_id,
                    "source_filepath": filepath,
                    "title": "Final Content Section",
                    "content": remaining_content,
                    "char_count": len(remaining_content),
                },
            )
        if remaining_content:
            self._log_debug(
                "Skipping final_content for '%s': len %d < min %d", filepath, len(remaining_content), min_chunk_len
            )
        return None

    def _generate_chunks_from_content(
        self, filepath: str, content: str, min_chunk_len: int, heading_levels: list[int]
    ) -> Generator["WebContentChunk", None, None]:
        """Generate WebContentChunk objects from a single document's content.

        This is the main orchestrator for segmenting one file.

        Args:
            filepath (str): The path of the source file being segmented.
            content (str): The full Markdown content of the file.
            min_chunk_len (int): The minimum character length for a chunk to be yielded.
            heading_levels (list[int]): A list of heading levels to use as delimiters.

        Yields:
            WebContentChunk: Individual chunks of content.
        """
        heading_regex, initial_content_regex = self._create_dynamic_regexes(heading_levels)
        initial_chunk: Optional["WebContentChunk"]
        current_pos: int
        initial_chunk, current_pos = self._yield_initial_or_full_content_chunk(
            filepath, content, min_chunk_len, initial_content_regex
        )
        num_chunks_yielded: int = 0
        if initial_chunk:
            yield initial_chunk
            num_chunks_yielded += 1
            if current_pos == len(content):
                return

        section_chunks: list["WebContentChunk"]
        section_chunks, current_pos = self._yield_section_chunks(
            filepath, content, min_chunk_len, heading_regex, current_pos
        )
        for chunk in section_chunks:
            yield chunk
            num_chunks_yielded += 1

        final_chunk: Optional["WebContentChunk"] = self._yield_final_content_chunk(
            filepath, content, min_chunk_len, current_pos, num_chunks_yielded
        )
        if final_chunk:
            yield final_chunk

    def pre_execution(self, shared_context: SLSharedContext) -> SegmentWebContentPreparedInputs:
        """Prepare the list of (filepath, content, params) tuples for segmentation.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.

        Returns:
            SegmentWebContentPreparedInputs: A list of tuples for the execution method.
                                             Returns an empty list if segmentation is skipped.
        """
        self._log_info("Preparing web content for segmentation.")
        config_data: dict[str, Any] = cast(dict[str, Any], shared_context.get("config", {}))
        flow_name: str = str(shared_context.get("current_operation_mode", "FL02_web_crawling"))
        flow_config: dict[str, Any] = config_data.get(flow_name, {})
        segmentation_opts: dict[str, Any] = flow_config.get("segmentation_options", {})

        seg_enabled: bool = bool(segmentation_opts.get("enabled", True))
        if not seg_enabled:
            self._log_info("Segmentation is disabled in configuration. Skipping segmentation node.")
            shared_context["web_content_chunks"] = []
            return []

        min_chunk_len: int = int(segmentation_opts.get("min_chunk_char_length", DEFAULT_MIN_CHUNK_CHAR_LENGTH))
        heading_levels_raw: list[Any] = segmentation_opts.get(
            "heading_levels_to_split_on", DEFAULT_HEADING_LEVELS_TO_SPLIT_ON
        )
        heading_levels: list[int] = sorted(
            set(h for h in heading_levels_raw if isinstance(h, int) and 1 <= h <= MAX_HEADING_LEVEL)
        )
        if not heading_levels:
            heading_levels = DEFAULT_HEADING_LEVELS_TO_SPLIT_ON

        self._log_info(
            "Segmentation parameters: min_chunk_length=%d, heading_levels=%s",
            min_chunk_len,
            heading_levels,
        )

        segmentation_params: dict[str, Any] = {"min_chunk_len": min_chunk_len, "heading_levels": heading_levels}
        files_data_any: Any = shared_context.get("files", [])
        if not isinstance(files_data_any, list):
            self._log_warning("'files' in shared_context is not a list. Cannot segment content.")
            shared_context["web_content_chunks"] = []
            return []

        prepared_data: SegmentWebContentPreparedInputs = []
        file_data_list: "FilePathContentList" = cast("FilePathContentList", files_data_any)

        for item in file_data_list:
            if (
                isinstance(item, tuple)
                and len(item) == EXPECTED_FILE_DATA_ITEM_LENGTH_WEB_CHUNK
                and isinstance(item[0], str)
                and isinstance(item[1], str)
            ):
                filepath_str: str = item[0]
                file_content_str: str = item[1]
                if file_content_str.strip():
                    prepared_data.append((filepath_str, file_content_str, segmentation_params))
                else:
                    self._log_debug("Skipping file '%s' for segmentation as it has no content.", filepath_str)
            else:
                self._log_warning(
                    "Invalid item format in shared_context['files'] for segmentation: %s. Expected (str, str).", item
                )
        if not prepared_data:
            self._log_warning("No valid files with content found for segmentation.")
            shared_context["web_content_chunks"] = []
        return prepared_data

    def execution(self, prepared_inputs: SegmentWebContentPreparedInputs) -> SegmentWebContentExecutionResult:
        """Segment the content of each fetched web document into chunks.

        Args:
            prepared_inputs (SegmentWebContentPreparedInputs): A list of tuples, each containing
                                                              (filepath, content, segmentation_params).

        Returns:
            SegmentWebContentExecutionResult: A list of `WebContentChunk` dictionaries.
        """
        self._log_info("Segmenting %d web documents...", len(prepared_inputs))
        all_chunks: SegmentWebContentExecutionResult = []
        if not prepared_inputs:
            return all_chunks

        for filepath, content, seg_params in prepared_inputs:
            min_len: int = seg_params["min_chunk_len"]
            levels: list[int] = seg_params["heading_levels"]
            self._log_debug("Segmenting content from: %s with min_len=%d, levels=%s", filepath, min_len, levels)
            try:
                file_chunks: list["WebContentChunk"] = list(
                    self._generate_chunks_from_content(filepath, content, min_len, levels)
                )
                all_chunks.extend(file_chunks)
                self._log_info("Segmented '%s' into %d chunks.", filepath, len(file_chunks))
            except (ValueError, TypeError, AttributeError, RuntimeError) as e_chunk:
                self._log_error("Failed to segment file '%s': %s", filepath, e_chunk, exc_info=True)

        self._log_info("Total %d web content chunks generated from all documents.", len(all_chunks))
        return all_chunks

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: SegmentWebContentPreparedInputs,
        execution_outputs: SegmentWebContentExecutionResult,
    ) -> None:
        """Store the list of generated web content chunks in the shared context.

        Args:
            shared_context (SLSharedContext): The shared context dictionary to update.
            prepared_inputs (SegmentWebContentPreparedInputs): The data from `pre_execution`.
            execution_outputs (SegmentWebContentExecutionResult): The list of `WebContentChunk`
                                                                  objects from `execution`.
        """
        del prepared_inputs
        shared_context["web_content_chunks"] = execution_outputs
        self._log_info("Stored %d web content chunks in shared_context['web_content_chunks'].", len(execution_outputs))


# End of src/FL02_web_crawling/nodes/n01b_segment_web_content.py
