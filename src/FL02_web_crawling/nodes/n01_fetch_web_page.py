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

"""Node responsible for fetching web page content using Crawl4AI.

This node handles fetching content from URLs, sitemaps, or specific
text/markdown files. For URL targets, it supports deep crawling up to a
specified `max_depth`. Fetched content is converted to Markdown
and saved to a specified output subdirectory. Special handling for YouTube
URLs limits crawl depth and adjusts output path and filename.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional
from urllib.parse import urlparse

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.utils.helpers import sanitize_filename

if TYPE_CHECKING:  # pragma: no cover
    from xml.etree.ElementTree import Element as XmlElement  # type: ignore[import-untyped]

    from crawl4ai import (  # type: ignore[import-untyped]
        AsyncWebCrawler as ImportedAsyncWebCrawlerC4AI,
    )
    from crawl4ai import (
        BrowserConfig as ImportedBrowserConfigC4AI,
    )
    from crawl4ai import (
        CrawlerRunConfig as ImportedCrawlerRunConfigC4AI,
    )
    from crawl4ai import (
        CrawlResult as ImportedCrawlResultC4AI,
    )
    from requests import Response as RequestsResponse  # type: ignore[import-untyped]

    from sourcelens.core.common_types import FilePathContentList


_module_logger_fetchweb: logging.Logger = logging.getLogger(__name__)

CRAWL4AI_AVAILABLE: bool = False
AsyncWebCrawler: Optional[type] = None
BrowserConfig: Optional[type] = None
CrawlerRunConfig: Optional[type] = None
CrawlResult: Optional[type] = None
BFSDeepCrawlStrategy: Optional[type] = None
requests_module: Optional[Any] = None
ElementTree_module: Optional[Any] = None


try:
    _module_logger_fetchweb.debug("Attempting to import 'xml.etree.ElementTree'...")
    from xml.etree import ElementTree as imported_ElementTree_xml

    ElementTree_module = imported_ElementTree_xml
    _module_logger_fetchweb.debug("'xml.etree.ElementTree' imported successfully.")

    _module_logger_fetchweb.debug("Attempting to import 'requests'...")
    import requests as imported_requests_http

    requests_module = imported_requests_http
    _module_logger_fetchweb.debug("'requests' imported successfully.")

    _module_logger_fetchweb.debug("Attempting to import from 'crawl4ai'...")
    from crawl4ai import (  # type: ignore[import-untyped]
        AsyncWebCrawler as ImportedAsyncWebCrawlerC4AI_real,
    )
    from crawl4ai import (
        BrowserConfig as ImportedBrowserConfigC4AI_real,
    )
    from crawl4ai import (
        CrawlerRunConfig as ImportedCrawlerRunConfigC4AI_real,
    )
    from crawl4ai import (
        CrawlResult as ImportedCrawlResultC4AI_real,
    )
    from crawl4ai.deep_crawling import (  # type: ignore[import-untyped]
        BFSDeepCrawlStrategy as ImportedBFSDeepCrawlStrategyC4AI_real,
    )

    AsyncWebCrawler = ImportedAsyncWebCrawlerC4AI_real
    BrowserConfig = ImportedBrowserConfigC4AI_real
    CrawlerRunConfig = ImportedCrawlerRunConfigC4AI_real
    CrawlResult = ImportedCrawlResultC4AI_real
    BFSDeepCrawlStrategy = ImportedBFSDeepCrawlStrategyC4AI_real
    _module_logger_fetchweb.info("Core Crawl4AI components imported successfully.")
    CRAWL4AI_AVAILABLE = True
except ImportError as e_import_crawl:  # pragma: no cover
    failed_module_name = e_import_crawl.name if hasattr(e_import_crawl, "name") and e_import_crawl.name else "dep"
    _module_logger_fetchweb.error(
        "Failed to import %s: %s. Web crawling will be disabled.", failed_module_name, e_import_crawl
    )
    CRAWL4AI_AVAILABLE = False


FetchWebPreparedInputs: TypeAlias = dict[str, Any]
FetchWebExecutionResult: TypeAlias = Optional[list[str]]
CrawlTargetInfo: TypeAlias = dict[str, str]
WebOptionsDict: TypeAlias = dict[str, Any]
CommonOutputConfigDict: TypeAlias = dict[str, Any]
ResolvedOutputPaths: TypeAlias = tuple[Path, Path]

DEFAULT_LOCAL_OUTPUT_DIR_NODE: Final[str] = "output"
PAGE_CONTENT_SUBDIR_NAME: Final[str] = "page_content"
DEFAULT_MAX_DEPTH_NODE: Final[int] = 1
SITEMAP_NAMESPACES_NODE: Final[dict[str, str]] = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
MAX_FILENAME_PART_LEN_NODE: Final[int] = 40
DEFAULT_PAGE_TIMEOUT_MS_NODE: Final[int] = 30000
DEFAULT_USER_AGENT_NODE: Final[str] = "SourceLensBot/0.1 (https://github.com/openXFlow/sourceLensAI)"
DEFAULT_CHECK_ROBOTS_NODE: Final[bool] = True

YOUTUBE_URL_PATTERNS_NODE: Final[list[re.Pattern[str]]] = [
    re.compile(r"(?:v=|\/|embed\/|watch\?v=|youtu\.be\/)([0-9A-Za-z_-]{11}).*"),
    re.compile(r"shorts\/([0-9A-Za-z_-]{11})"),
]


def _is_youtube_url_in_node(url: Optional[str]) -> bool:
    """Check if the given URL is a YouTube video URL.

    Args:
        url: The URL string to check.

    Returns:
        True if the URL matches known YouTube video patterns, False otherwise.
    """
    if not url:
        return False
    return any(pattern.search(url) for pattern in YOUTUBE_URL_PATTERNS_NODE)


class FetchWebPage(BaseNode[FetchWebPreparedInputs, FetchWebExecutionResult]):
    """Fetch web content, convert to Markdown, and save locally.

    Uses `crawl4ai`. Handles deep crawling for general URLs and specific
    output for YouTube page content.
    """

    shared_context_during_execution: SLSharedContext

    def __init__(self, max_retries: int = 1, wait: int = 5) -> None:
        """Initialize the FetchWebPage node.

        Args:
            max_retries: Max retries for the node's `execution` phase.
            wait: Wait time between retries in seconds for `execution`.
        """
        super().__init__(max_retries=max_retries, wait=wait)
        self.shared_context_during_execution = {}
        if not CRAWL4AI_AVAILABLE:  # pragma: no cover
            self._log_error("FetchWebPage init: Crawl4AI unavailable. Web crawling will be skipped.")

    def _determine_crawl_target_and_initial_skip(
        self, shared_context: SLSharedContext
    ) -> tuple[Optional[CrawlTargetInfo], Optional[str]]:
        """Determine crawl target and if initial skip is needed.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A tuple: (crawl_target_info_or_none, skip_reason_or_none).
        """
        if not CRAWL4AI_AVAILABLE:  # pragma: no cover
            return None, "Crawl4AI library not available."

        crawl_target: Optional[CrawlTargetInfo] = None
        if "crawl_url" in shared_context and shared_context["crawl_url"]:
            crawl_target = {"type": "url", "value": str(shared_context["crawl_url"])}
        elif "crawl_sitemap" in shared_context and shared_context["crawl_sitemap"]:  # pragma: no cover
            crawl_target = {"type": "sitemap", "value": str(shared_context["crawl_sitemap"])}
        elif "crawl_file" in shared_context and shared_context["crawl_file"]:  # pragma: no cover
            crawl_target = {"type": "file", "value": str(shared_context["crawl_file"])}

        if not crawl_target:
            return None, "No web crawl target specified."
        return crawl_target, None

    def _resolve_output_paths_for_target(self, shared_context: SLSharedContext) -> Path:
        """Resolve the specific output path for crawled content from this node.

        Args:
            shared_context: The shared context.

        Returns:
            The Path object for the directory where this node will save its files.
        """
        project_name_for_dir: str = str(shared_context.get("project_name", "unknown_project"))
        base_output_dir_str: str = str(shared_context.get("output_dir", DEFAULT_LOCAL_OUTPUT_DIR_NODE))
        run_specific_output_dir = Path(base_output_dir_str) / project_name_for_dir
        content_output_path = run_specific_output_dir / PAGE_CONTENT_SUBDIR_NAME

        if not shared_context.get("final_output_dir_web_crawl"):
            shared_context["final_output_dir_web_crawl"] = str(run_specific_output_dir)

        self._log_info("Target output directory for FetchWebPage files: %s", content_output_path.resolve())
        return content_output_path

    def _determine_crawl_parameters(
        self, shared_context: SLSharedContext, web_opts: WebOptionsDict, *, is_youtube_target_url: bool
    ) -> dict[str, Any]:
        """Determine crawl parameters based on context and config.

        Args:
            shared_context: The shared context.
            web_opts: Crawler options from config.
            is_youtube_target_url: True if the target is a YouTube URL.

        Returns:
            A dictionary of resolved crawl parameters.
        """
        cli_depth_override_val: Any = shared_context.get("cli_crawl_depth")
        cli_depth: Optional[int] = int(cli_depth_override_val) if cli_depth_override_val is not None else None
        max_depth_cfg: int = int(web_opts.get("max_depth_recursive", DEFAULT_MAX_DEPTH_NODE))
        final_max_depth = 0 if is_youtube_target_url else (cli_depth if cli_depth is not None else max_depth_cfg)

        if is_youtube_target_url:
            self._log_info("YT URL for FetchWebPage. Forcing max_depth to 0 for HTML page content.")

        processing_mode: str = str(web_opts.get("processing_mode", "minimalistic"))
        self._log_info("FetchWebPage pre_execution: processing_mode: '%s'", processing_mode)

        return {
            "max_depth": final_max_depth,
            "user_agent": str(web_opts.get("user_agent", DEFAULT_USER_AGENT_NODE)),
            "page_timeout_ms": int(web_opts.get("default_page_timeout_ms", DEFAULT_PAGE_TIMEOUT_MS_NODE)),
            "check_robots_txt": bool(web_opts.get("respect_robots_txt", DEFAULT_CHECK_ROBOTS_NODE)),
            "processing_mode": processing_mode,
        }

    def pre_execution(self, shared_context: SLSharedContext) -> FetchWebPreparedInputs:
        """Prepare parameters for web crawling.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary with parameters for execution, or `{"skip": True}`.
        """
        self._log_info("Preparing for web page fetching...")
        self.shared_context_during_execution = shared_context

        crawl_target, skip_reason = self._determine_crawl_target_and_initial_skip(shared_context)
        if skip_reason or not crawl_target:
            return {"skip": True, "reason": skip_reason or "Unknown reason"}

        config_val: Any = self._get_required_shared(shared_context, "config")
        config: dict[str, Any] = config_val if isinstance(config_val, dict) else {}
        flow_name: str = str(shared_context.get("current_operation_mode", "FL02_web_crawling"))
        web_flow_settings: dict[str, Any] = config.get(flow_name, {})
        web_opts: WebOptionsDict = web_flow_settings.get("crawler_options", {})

        is_youtube_target_url_flag: bool = _is_youtube_url_in_node(crawl_target["value"])
        output_path_for_this_node_files = self._resolve_output_paths_for_target(shared_context)
        crawl_params = self._determine_crawl_parameters(
            shared_context, web_opts, is_youtube_target_url=is_youtube_target_url_flag
        )

        return {
            "skip": False,
            "crawl_target": crawl_target,
            "output_path_for_node_files": output_path_for_this_node_files,
            "is_youtube_target": is_youtube_target_url_flag,
            **crawl_params,
        }

    async def _save_markdown_from_result(
        self,
        crawl_result: "ImportedCrawlResultC4AI",
        base_save_dir: Path,
        *,  # Make subsequent arguments keyword-only
        is_youtube_target: bool,
        depth_override: Optional[int] = None,
    ) -> Optional[Path]:
        """Save Markdown content from a CrawlResult to a structured file path.

        Args:
            crawl_result: The CrawlResult object from crawl4ai.
            base_save_dir: Base directory for saving files from this node's run.
            is_youtube_target: True if the original crawl target was a YouTube URL.
            depth_override: Optional depth; if None, uses depth from metadata.

        Returns:
            The absolute path to the saved Markdown file if successful, else None.
        """
        if not (
            hasattr(crawl_result, "success")
            and crawl_result.success
            and hasattr(crawl_result, "markdown")
            and crawl_result.markdown
            and hasattr(crawl_result, "url")
        ):
            url_attr = getattr(crawl_result, "url", "Unknown URL")
            self._log_warning("CrawlResult for '%s' missing data. Cannot save.", str(url_attr))
            return None

        page_url_str = str(crawl_result.url)
        markdown_content = str(crawl_result.markdown)
        page_url_obj = urlparse(page_url_str)
        depth = (
            depth_override if depth_override is not None else int(getattr(crawl_result, "metadata", {}).get("depth", 0))
        )

        final_filename: str
        save_subdir = base_save_dir

        if is_youtube_target:
            sanitized_yt_title = str(
                self.shared_context_during_execution.get("current_youtube_sanitized_title", "yt_page")
            )
            final_filename = f"pg_{sanitized_yt_title}.md"
            self._log_info("YouTube page content filename: %s", final_filename)
        else:
            relative_page_path = Path(page_url_obj.path.lstrip("/"))
            page_name_base: str
            if not relative_page_path.name or str(relative_page_path).endswith("/"):
                page_name_base = "index"
                save_subdir = base_save_dir / relative_page_path
            else:
                page_name_base = relative_page_path.stem
                save_subdir = base_save_dir / relative_page_path.parent
            final_filename = f"h{depth}_{sanitize_filename(page_name_base, max_len=50)}.md"

        filepath_to_save = save_subdir / final_filename
        try:
            filepath_to_save.parent.mkdir(parents=True, exist_ok=True)
            filepath_to_save.write_text(markdown_content, encoding="utf-8")
            self._log_info("Saved Markdown for '%s' (depth %d) to %s", page_url_str, depth, filepath_to_save)
            return filepath_to_save.resolve()
        except OSError as e_write:  # pragma: no cover
            self._log_error("Failed to write file %s: %s", filepath_to_save, e_write)
            return None

    async def _crawl_sitemap_urls(  # pragma: no cover
        self,
        crawler: "ImportedAsyncWebCrawlerC4AI",
        sitemap_url: str,
        output_path_base: Path,
        run_config_single_page: "ImportedCrawlerRunConfigC4AI",
    ) -> list[Path]:
        """Fetch URLs from sitemap and crawl each as a single page.

        Args:
            crawler: An instance of `crawl4ai.AsyncWebCrawler`.
            sitemap_url: The URL of the sitemap.xml.
            output_path_base: Base directory for saving files.
            run_config_single_page: CrawlerRunConfig for single page fetches.

        Returns:
            A list of absolute paths to successfully saved files.
        """
        self._log_info("Fetching sitemap: %s", sitemap_url)
        if not requests_module or not ElementTree_module:
            self._log_error("Sitemap processing requires 'requests' and 'xml.etree'. Skipping.")
            return []
        try:
            if not callable(getattr(requests_module, "get", None)):
                self._log_error("'requests.get' not callable. Cannot fetch sitemap.")
                return []
            response: "RequestsResponse" = requests_module.get(sitemap_url, timeout=30)
            response.raise_for_status()
            root: "XmlElement" = ElementTree_module.fromstring(response.content)
            urls_sitemap = [loc.text for loc in root.findall(".//ns:loc", SITEMAP_NAMESPACES_NODE) if loc.text]
            self._log_info("Found %d URLs in sitemap. Crawling each...", len(urls_sitemap))
            saved_files: list[Path] = []
            for url_entry in urls_sitemap:
                self._log_info("Crawling sitemap URL: %s", url_entry)
                try:
                    res_item: "ImportedCrawlResultC4AI" = await crawler.arun(
                        url=url_entry, config=run_config_single_page
                    )
                    # For sitemap entries, is_youtube_target should be False
                    saved_p = await self._save_markdown_from_result(
                        res_item, output_path_base, is_youtube_target=False, depth_override=0
                    )
                    if saved_p:
                        saved_files.append(saved_p)
                except (IOError, OSError, RuntimeError, ValueError, TypeError) as e_sm_crawl:
                    self._log_error("Error crawling sitemap URL '%s': %s", url_entry, e_sm_crawl, exc_info=True)
            return saved_files
        except (requests_module.RequestException, ElementTree_module.ParseError, AttributeError) as e_sitemap:  # type: ignore[union-attr]
            self._log_error(
                "Failed sitemap processing for %s (%s): %s", sitemap_url, type(e_sitemap).__name__, e_sitemap
            )
        return []

    async def _handle_url_target_async(
        self, crawler: "ImportedAsyncWebCrawlerC4AI", target_value: str, prepared_inputs: FetchWebPreparedInputs
    ) -> list[Path]:
        """Handle crawling for a 'url' target type, including deep crawl.

        Args:
            crawler: The AsyncWebCrawler instance.
            target_value: The target URL to crawl.
            prepared_inputs: Parameters from pre_execution.

        Returns:
            List of absolute paths to saved Markdown files.
        """
        output_path_base = prepared_inputs["output_path_for_node_files"]
        is_yt = prepared_inputs["is_youtube_target"]
        max_depth = prepared_inputs["max_depth"]
        page_timeout = prepared_inputs["page_timeout_ms"]
        check_robots = prepared_inputs["check_robots_txt"]
        saved_files_abs: list[Path] = []

        self._log_info("Starting URL crawl for '%s', effective max_depth: %d", target_value, max_depth)
        assert BFSDeepCrawlStrategy is not None and CrawlerRunConfig is not None
        strategy = BFSDeepCrawlStrategy(max_depth=max_depth, include_external=False)
        run_cfg_args: dict[str, Any] = {
            "deep_crawl_strategy": strategy,
            "page_timeout": page_timeout,
            "check_robots_txt": check_robots,
        }
        run_cfg = CrawlerRunConfig(**run_cfg_args)

        results_list: list["ImportedCrawlResultC4AI"] = await crawler.arun(url=target_value, config=run_cfg)
        for result_item in results_list:
            saved_path = await self._save_markdown_from_result(result_item, output_path_base, is_youtube_target=is_yt)
            if saved_path:
                saved_files_abs.append(saved_path)
        return saved_files_abs

    async def _handle_file_target_async(  # pragma: no cover
        self, crawler: "ImportedAsyncWebCrawlerC4AI", target_value: str, prepared_inputs: FetchWebPreparedInputs
    ) -> list[Path]:
        """Handle crawling for a 'file' target type (remote or local).

        Args:
            crawler: The AsyncWebCrawler instance.
            target_value: The file URL or local path.
            prepared_inputs: Parameters from pre_execution.

        Returns:
            List of absolute paths to saved Markdown files (usually one).
        """
        output_path_base = prepared_inputs["output_path_for_node_files"]
        page_timeout = prepared_inputs["page_timeout_ms"]
        check_robots = prepared_inputs["check_robots_txt"]
        saved_files_abs: list[Path] = []
        assert CrawlerRunConfig is not None

        if target_value.startswith(("http://", "https://")):
            self._log_info("Fetching remote file as single page: %s", target_value)
            run_cfg_args = {"page_timeout": page_timeout, "check_robots_txt": check_robots}
            run_cfg = CrawlerRunConfig(**run_cfg_args)
            result_item_remote: "ImportedCrawlResultC4AI" = await crawler.arun(url=target_value, config=run_cfg)
            saved_path_remote = await self._save_markdown_from_result(
                result_item_remote, output_path_base, is_youtube_target=False, depth_override=0
            )
            if saved_path_remote:
                saved_files_abs.append(saved_path_remote)
        else:
            self._log_info("Processing local file: %s", target_value)
            local_file_path = Path(target_value)
            if local_file_path.is_file():
                try:
                    content = local_file_path.read_text(encoding="utf-8")
                    mock_crawl_result_dict: dict[str, Any] = {
                        "url": local_file_path.as_uri(),
                        "markdown": content,
                        "success": True,
                        "metadata": {"depth": 0},
                    }

                    class MockCrawlResultLocal:
                        def __init__(self, data: dict[str, Any]) -> None:
                            self.__dict__.update(data)
                            for attr_name in ["url", "markdown", "success", "metadata"]:
                                if not hasattr(self, attr_name):
                                    setattr(self, attr_name, None)

                    mock_res_obj = MockCrawlResultLocal(mock_crawl_result_dict)
                    saved_md_path = await self._save_markdown_from_result(
                        mock_res_obj,
                        output_path_base,
                        is_youtube_target=False,
                        depth_override=0,  # type: ignore[arg-type]
                    )
                    if saved_md_path:
                        saved_files_abs.append(saved_md_path.resolve())
                except OSError as e_rw:
                    self._log_error("Error reading/writing local file %s: %s", local_file_path, e_rw)
            else:
                self._log_warning("Local file path '%s' not found. Skipping.", target_value)
        return saved_files_abs

    async def _execute_crawling_async(self, prepared_inputs: FetchWebPreparedInputs) -> FetchWebExecutionResult:
        """Asynchronous execution logic for crawling.

        Args:
            prepared_inputs: Parameters from `pre_execution`.

        Returns:
            List of absolute paths to saved files, or None on failure.
        """
        if not all([AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, BFSDeepCrawlStrategy]):  # pragma: no cover
            self._log_error("Crawl4AI components unavailable. Cannot execute crawl.")
            return None

        crawl_target: dict[str, str] = prepared_inputs["crawl_target"]
        user_agent_str: str = prepared_inputs["user_agent"]
        saved_file_paths_abs: list[Path] = []

        assert BrowserConfig is not None and AsyncWebCrawler is not None
        browser_cfg: "ImportedBrowserConfigC4AI" = BrowserConfig(
            headless=True, user_agent=user_agent_str, verbose=False
        )
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            target_type, target_value = crawl_target.get("type"), crawl_target["value"]
            if target_type == "url":
                saved_file_paths_abs = await self._handle_url_target_async(crawler, target_value, prepared_inputs)
            elif target_type == "sitemap":  # pragma: no cover
                assert CrawlerRunConfig is not None
                run_cfg_single = CrawlerRunConfig(
                    page_timeout=prepared_inputs["page_timeout_ms"],
                    check_robots_txt=prepared_inputs["check_robots_txt"],
                )
                saved_file_paths_abs = await self._crawl_sitemap_urls(
                    crawler, target_value, prepared_inputs["output_path_for_node_files"], run_cfg_single
                )
            elif target_type == "file":  # pragma: no cover
                saved_file_paths_abs = await self._handle_file_target_async(crawler, target_value, prepared_inputs)
            else:  # pragma: no cover
                self._log_warning("Unknown crawl target type: %s", target_type)
        return [str(p) for p in saved_file_paths_abs]

    def execution(self, prepared_inputs: FetchWebPreparedInputs) -> FetchWebExecutionResult:
        """Execute web crawling based on prepared inputs.

        Args:
            prepared_inputs: Parameters from `pre_execution`.

        Returns:
            List of absolute paths to saved files, or None on failure/skip.
        """
        if prepared_inputs.get("skip", True):
            self._log_info("Skipping web page fetching. Reason: %s", str(prepared_inputs.get("reason", "N/A")))
            return None

        self._log_info("Executing web page fetching...")
        output_path_base_target: Path = prepared_inputs["output_path_for_node_files"]
        try:
            output_path_base_target.mkdir(parents=True, exist_ok=True)
            self._log_info("Ensured output directory exists: %s", output_path_base_target.resolve())
        except OSError as e_dir:  # pragma: no cover
            self._log_error("Failed to create target output dir %s: %s.", output_path_base_target, e_dir)
            return None
        result: FetchWebExecutionResult = None
        try:
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("httpcore").setLevel(logging.WARNING)
            result = asyncio.run(self._execute_crawling_async(prepared_inputs))
        except (IOError, OSError, AttributeError, TypeError, ValueError) as e:  # pragma: no cover
            self._log_error("Error during async web crawling: %s", e, exc_info=True)
        except RuntimeError as e_rt:  # pragma: no cover
            self._log_error("RuntimeError during asyncio (nested loops?): %s.", e_rt, exc_info=True)
        finally:
            logging.getLogger("httpx").setLevel(logging.NOTSET)
            logging.getLogger("httpcore").setLevel(logging.NOTSET)
        return result

    def _handle_llm_extended_processing(
        self, shared_context: SLSharedContext, saved_files_abs: list[str], intended_output_dir: Path
    ) -> None:
        """Populate `shared_context["files"]` for "llm_extended" mode.

        Args:
            shared_context: The shared context dictionary.
            saved_files_abs: List of absolute paths to saved crawled files.
            intended_output_dir: Absolute base directory where files were saved.
        """
        self._log_info("LLM_EXTENDED mode: Populating shared_context['files'] with crawled content.")
        files_for_pipeline_any: Any = shared_context.get("files", [])
        files_for_pipeline: "FilePathContentList" = (
            files_for_pipeline_any if isinstance(files_for_pipeline_any, list) else []
        )
        abs_intended_output_dir = intended_output_dir.resolve()
        num_added = 0
        for file_path_str in saved_files_abs:
            try:
                file_path_abs = Path(file_path_str).resolve()
                if not file_path_abs.is_file():
                    continue  # pragma: no cover
                relative_path_for_context = file_path_abs.relative_to(abs_intended_output_dir)
                content = file_path_abs.read_text(encoding="utf-8")
                files_for_pipeline.append((relative_path_for_context.as_posix(), content))
                self._log_debug("Added to pipeline by FetchWebPage: '%s'", relative_path_for_context.as_posix())
                num_added += 1
            except (OSError, ValueError, TypeError) as e_read:  # pragma: no cover
                self._log_error("Failed to read/process crawled file %s for pipeline: %s", file_path_str, e_read)
        shared_context["files"] = files_for_pipeline
        self._log_info("FetchWebPage added %d crawled files to shared_context['files'].", num_added)

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: FetchWebPreparedInputs,
        execution_outputs: FetchWebExecutionResult,
    ) -> None:
        """Store paths of saved files and conditionally populate `shared_context["files"]`.

        Args:
            shared_context: The shared context dictionary.
            prepared_inputs: Parameters from `pre_execution`.
            execution_outputs: List of saved file paths, or None.
        """
        output_path_base_for_target: Path = prepared_inputs["output_path_for_node_files"]
        if prepared_inputs.get("skip", True):  # pragma: no cover
            self._log_info("Web page fetching skipped by FetchWebPage. No files processed.")
            shared_context.setdefault("files", [])
            return

        saved_files_abs: list[str] = [str(p) for p in (execution_outputs or []) if isinstance(p, (str, Path))]
        if saved_files_abs:
            self._log_info(
                "FetchWebPage successfully saved %d files to %s.", len(saved_files_abs), output_path_base_for_target
            )
            processing_mode = str(prepared_inputs.get("processing_mode", "minimalistic"))
            self._log_info("FetchWebPage post_execution: Processing_mode: '%s'", processing_mode)
            if processing_mode == "llm_extended":
                self._handle_llm_extended_processing(shared_context, saved_files_abs, output_path_base_for_target)
            else:
                current_files_val: Any = shared_context.get("files", [])  # Ensure 'files' is initialized if needed
                current_files: "FilePathContentList" = current_files_val if isinstance(current_files_val, list) else []
                shared_context["files"] = current_files
                self._log_info("Minimalistic mode (FetchWebPage): shared_context['files'] not populated by this node.")
        elif execution_outputs is not None:  # pragma: no cover
            self._log_warning("FetchWebPage execution ran but no files were saved.")
            shared_context.setdefault("files", [])
        else:  # pragma: no cover
            self._log_error("FetchWebPage execution failed. Check previous logs.")
            shared_context.setdefault("files", [])


# End of src/FL02_web_crawling/nodes/n01_fetch_web_page.py
