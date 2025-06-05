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
and saved to a specified output subdirectory.
"""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional
from urllib.parse import urlparse

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.utils.helpers import sanitize_filename

if TYPE_CHECKING:
    from sourcelens.core.common_types import FilePathContentList


_module_logger_fetchweb: logging.Logger = logging.getLogger(__name__)

CRAWL4AI_AVAILABLE: bool = False
AsyncWebCrawler: Optional[Any] = None
BrowserConfig: Optional[Any] = None
CrawlerRunConfig: Optional[Any] = None
CrawlResult: Optional[Any] = None
BFSDeepCrawlStrategy: Optional[Any] = None
requests_module: Optional[Any] = None
ElementTree_module: Optional[Any] = None


try:
    _module_logger_fetchweb.debug("Attempting to import 'xml.etree.ElementTree'...")
    from xml.etree import ElementTree as imported_ElementTree_xml  # type: ignore[import-untyped]

    ElementTree_module = imported_ElementTree_xml
    _module_logger_fetchweb.debug("'xml.etree.ElementTree' imported successfully.")

    _module_logger_fetchweb.debug("Attempting to import 'requests'...")
    import requests as imported_requests_http  # type: ignore[import-untyped]

    requests_module = imported_requests_http
    _module_logger_fetchweb.debug("'requests' imported successfully.")

    _module_logger_fetchweb.debug("Attempting to import from 'crawl4ai'...")
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
    from crawl4ai.deep_crawling import (  # type: ignore[import-untyped]
        BFSDeepCrawlStrategy as ImportedBFSDeepCrawlStrategyC4AI,
    )

    AsyncWebCrawler = ImportedAsyncWebCrawlerC4AI
    BrowserConfig = ImportedBrowserConfigC4AI
    CrawlerRunConfig = ImportedCrawlerRunConfigC4AI
    CrawlResult = ImportedCrawlResultC4AI
    BFSDeepCrawlStrategy = ImportedBFSDeepCrawlStrategyC4AI

    _module_logger_fetchweb.info("Core Crawl4AI components imported successfully.")
    CRAWL4AI_AVAILABLE = True
except ImportError as e_import_crawl:
    failed_module_name_str: str = (
        e_import_crawl.name if hasattr(e_import_crawl, "name") and e_import_crawl.name else "a Crawl4AI dependency"
    )
    _module_logger_fetchweb.error(
        "Failed to import %s: %s. Web crawling functionality will be disabled.", failed_module_name_str, e_import_crawl
    )
    CRAWL4AI_AVAILABLE = False


# Type Aliases
FetchWebPreparedInputs: TypeAlias = dict[str, Any]
FetchWebExecutionResult: TypeAlias = Optional[list[str]]

# Constants
DEFAULT_LOCAL_OUTPUT_DIR_NODE: Final[str] = "output"
DEFAULT_WEB_OUTPUT_SUBDIR_NODE: Final[str] = "crawled_web_pages"
DEFAULT_MAX_DEPTH_NODE: Final[int] = 1
SITEMAP_NAMESPACES_NODE: Final[dict[str, str]] = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
MAX_DOMAIN_PATH_LEN_FOR_SUBDIR_NODE: Final[int] = 50
DEFAULT_PAGE_TIMEOUT_MS_NODE: Final[int] = 30000
DEFAULT_USER_AGENT_NODE: Final[str] = "SourceLensBot/0.1 (https://github.com/openXFlow/sourceLensAI)"
DEFAULT_CHECK_ROBOTS_NODE: Final[bool] = True


class FetchWebPage(BaseNode[FetchWebPreparedInputs, FetchWebExecutionResult]):
    """Fetches web content, supports deep crawling, converts to Markdown, and saves locally."""

    def __init__(self, max_retries: int = 1, wait: int = 5) -> None:
        """Initialize the FetchWebPage node.

        Args:
            max_retries (int): Max retries for the node's `execution` phase.
            wait (int): Wait time between retries in seconds for the node's `execution` phase.
        """
        super().__init__(max_retries=max_retries, wait=wait)
        if not CRAWL4AI_AVAILABLE:
            self._log_error("FetchWebPage initialized, but Crawl4AI is not available. Web crawling will be skipped.")

    def _get_crawl_target(self, shared_context: SLSharedContext) -> Optional[dict[str, Any]]:
        """Determine the crawl target (URL, sitemap, file) from shared_context.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.

        Returns:
            Optional[dict[str, Any]]: A dictionary with 'type' and 'value' of the crawl target,
                                      or None if no target is specified.
        """
        if "crawl_url" in shared_context and shared_context["crawl_url"]:
            return {"type": "url", "value": str(shared_context["crawl_url"])}
        if "crawl_sitemap" in shared_context and shared_context["crawl_sitemap"]:
            return {"type": "sitemap", "value": str(shared_context["crawl_sitemap"])}
        if "crawl_file" in shared_context and shared_context["crawl_file"]:
            return {"type": "file", "value": str(shared_context["crawl_file"])}
        return None

    def pre_execution(self, shared_context: SLSharedContext) -> FetchWebPreparedInputs:
        """Prepare parameters for web crawling, including deep crawl settings.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.

        Returns:
            FetchWebPreparedInputs: A dictionary with parameters for the execution phase.
        """
        self._log_info("Preparing for web page fetching...")
        shared_context["final_output_dir_web_crawl"] = None

        if not CRAWL4AI_AVAILABLE:
            self._log_warning("Crawl4AI library not available. Skipping web fetch pre_execution steps.")
            return {"skip": True, "reason": "Crawl4AI library not available."}

        crawl_target: Optional[dict[str, Any]] = self._get_crawl_target(shared_context)
        if not crawl_target:
            self._log_info("No web crawl target specified. Skipping web fetch.")
            return {"skip": True, "reason": "No web crawl target specified."}

        config_val: Any = self._get_required_shared(shared_context, "config")
        config: dict[str, Any] = config_val if isinstance(config_val, dict) else {}

        flow_name: str = str(shared_context.get("current_operation_mode", "FL02_web_crawling"))
        web_flow_settings: dict[str, Any] = config.get(flow_name, {})
        web_opts_val: Any = web_flow_settings.get("crawler_options", {})
        web_opts: dict[str, Any] = web_opts_val if isinstance(web_opts_val, dict) else {}

        common_settings_val: Any = config.get("common", {})
        common_settings: dict[str, Any] = common_settings_val if isinstance(common_settings_val, dict) else {}
        common_output_val: Any = common_settings.get("common_output_settings", {})
        common_output_config: dict[str, Any] = common_output_val if isinstance(common_output_val, dict) else {}

        base_output_dir_str: str = str(common_output_config.get("main_output_directory", DEFAULT_LOCAL_OUTPUT_DIR_NODE))
        cli_subdir_override: Optional[Any] = shared_context.get("cli_crawl_output_subdir")
        default_web_content_subdir: str = (
            str(cli_subdir_override)
            if cli_subdir_override and isinstance(cli_subdir_override, str)
            else str(web_opts.get("default_output_subdir_name", DEFAULT_WEB_OUTPUT_SUBDIR_NODE))
        )

        crawl_target_value_str: str = str(crawl_target["value"])
        parsed_url_target: Any = urlparse(crawl_target_value_str)
        domain_name_target: str = parsed_url_target.netloc or "local_file_or_unknown"
        path_name_target: str = parsed_url_target.path.strip("/").replace("/", "_") or "index"
        raw_target_name_for_dir: str = f"{domain_name_target}_{path_name_target}"

        specific_target_subdir_name_raw: str = sanitize_filename(raw_target_name_for_dir)
        specific_target_subdir_name_domain: str = sanitize_filename(domain_name_target)
        specific_target_subdir_name: str = (
            specific_target_subdir_name_raw[:MAX_DOMAIN_PATH_LEN_FOR_SUBDIR_NODE]
            or specific_target_subdir_name_domain[:MAX_DOMAIN_PATH_LEN_FOR_SUBDIR_NODE]
            or "crawled_site"
        )

        output_path_for_target: Path = (
            Path(base_output_dir_str) / default_web_content_subdir / specific_target_subdir_name
        )
        shared_context["final_output_dir_web_crawl"] = str(output_path_for_target.resolve())
        self._log_info("Target output directory for this crawl: %s", output_path_for_target.resolve())

        cli_depth_override_val: Any = shared_context.get("cli_crawl_depth")
        max_depth_from_config: int = int(web_opts.get("max_depth_recursive", DEFAULT_MAX_DEPTH_NODE))
        max_depth_val: int = (
            int(cli_depth_override_val)
            if cli_depth_override_val is not None and isinstance(cli_depth_override_val, int)
            else max_depth_from_config
        )

        processing_mode_val: Any = web_opts.get("processing_mode", "minimalistic")
        processing_mode: str = str(processing_mode_val)
        self._log_info("FetchWebPage pre_execution: Determined processing_mode for this run: '%s'", processing_mode)

        return {
            "skip": False,
            "crawl_target": crawl_target,
            "output_path_base_for_target": output_path_for_target,
            "max_depth": max_depth_val,
            "user_agent": str(web_opts.get("user_agent", DEFAULT_USER_AGENT_NODE)),
            "page_timeout_ms": int(web_opts.get("default_page_timeout_ms", DEFAULT_PAGE_TIMEOUT_MS_NODE)),
            "check_robots_txt": bool(web_opts.get("respect_robots_txt", DEFAULT_CHECK_ROBOTS_NODE)),
            "processing_mode": processing_mode,
        }

    async def _save_markdown_from_result(
        self, crawl_result: Any, base_save_dir: Path, depth_override: Optional[int] = None
    ) -> Optional[Path]:
        """Save Markdown content from a CrawlResult object to a structured file path.

        Args:
            crawl_result (Any): The CrawlResult object from crawl4ai.
            base_save_dir (Path): The base directory for saving this specific crawl target's files.
            depth_override (Optional[int]): Optional depth to use; if None, uses depth from metadata.

        Returns:
            Optional[Path]: The absolute path to the saved Markdown file if successful, else None.
        """
        if not (
            hasattr(crawl_result, "success")
            and crawl_result.success
            and hasattr(crawl_result, "markdown")
            and crawl_result.markdown
            and hasattr(crawl_result, "url")
        ):
            self._log_warning(
                "CrawlResult missing success, markdown, or URL. Cannot save. URL: %s",
                getattr(crawl_result, "url", "Unknown URL"),
            )
            return None

        page_url_str: str = str(crawl_result.url)
        markdown_content: str = str(crawl_result.markdown)

        page_url_obj: Any = urlparse(page_url_str)
        depth: int
        if depth_override is not None:
            depth = depth_override
        elif hasattr(crawl_result, "metadata") and isinstance(crawl_result.metadata, dict):
            depth = int(crawl_result.metadata.get("depth", 0))
        else:
            depth = 0

        relative_page_path_from_site_root: Path = Path(page_url_obj.path.lstrip("/"))
        page_name_base: str
        save_subdir: Path

        if not relative_page_path_from_site_root.name or str(relative_page_path_from_site_root).endswith("/"):
            page_name_base = "index"
            save_subdir = base_save_dir / relative_page_path_from_site_root
        else:
            page_name_base = relative_page_path_from_site_root.stem
            save_subdir = base_save_dir / relative_page_path_from_site_root.parent

        final_filename: str = f"h{depth}_{sanitize_filename(page_name_base, max_len=50)}.md"
        filepath_to_save: Path = save_subdir / final_filename

        try:
            filepath_to_save.parent.mkdir(parents=True, exist_ok=True)
            filepath_to_save.write_text(markdown_content, encoding="utf-8")
            self._log_info("Saved Markdown for '%s' (depth %d) to %s", page_url_str, depth, filepath_to_save)
            return filepath_to_save.resolve()
        except OSError as e_write:
            self._log_error("Failed to write file %s: %s", filepath_to_save, e_write)
            return None

    async def _crawl_sitemap_urls(
        self, crawler: Any, sitemap_url: str, output_path_base: Path, run_config_single_page: Any
    ) -> list[Path]:
        """Fetch URLs from sitemap and crawl each as a single page.

        Args:
            crawler (Any): An instance of `crawl4ai.AsyncWebCrawler`.
            sitemap_url (str): The URL of the sitemap.xml.
            output_path_base (Path): The base directory for saving files.
            run_config_single_page (Any): CrawlerRunConfig for single page fetches.

        Returns:
            list[Path]: A list of absolute paths to successfully saved files.
        """
        self._log_info("Fetching sitemap: %s", sitemap_url)
        if not requests_module or not ElementTree_module:
            self._log_error("Sitemap processing requires 'requests' and 'xml.etree.ElementTree'. Skipping.")
            return []
        try:
            if not callable(getattr(requests_module, "get", None)):
                self._log_error("'requests.get' is not callable. Cannot fetch sitemap.")
                return []

            response: Any = requests_module.get(sitemap_url, timeout=30)
            response.raise_for_status()
            root: Any = ElementTree_module.fromstring(response.content)
            urls_from_sitemap: list[str] = [
                loc.text for loc in root.findall(".//ns:loc", SITEMAP_NAMESPACES_NODE) if loc.text
            ]
            self._log_info("Found %d URLs in sitemap. Crawling each as a single page...", len(urls_from_sitemap))

            saved_files: list[Path] = []
            for url_entry in urls_from_sitemap:
                self._log_info("Crawling sitemap URL: %s", url_entry)
                try:
                    result_item: Any = await crawler.arun(url=url_entry, config=run_config_single_page)
                    saved_path: Optional[Path] = await self._save_markdown_from_result(
                        result_item, output_path_base, depth_override=0
                    )
                    if saved_path:
                        saved_files.append(saved_path)
                except (IOError, OSError, RuntimeError, ValueError, TypeError) as e_sitemap_crawl:
                    self._log_error(
                        "Error crawling individual sitemap URL '%s': %s", url_entry, e_sitemap_crawl, exc_info=True
                    )
            return saved_files
        except (requests_module.RequestException, ElementTree_module.ParseError, AttributeError) as e:
            module_name: str = type(e).__name__
            self._log_error("Failed during sitemap processing for %s (%s): %s", sitemap_url, module_name, e)
        return []

    async def _handle_url_target_async(
        self, crawler: Any, target_value: str, prepared_inputs: FetchWebPreparedInputs
    ) -> list[Path]:
        """Handle crawling for a 'url' target type, including deep crawl.

        Args:
            crawler (Any): The AsyncWebCrawler instance.
            target_value (str): The target URL to crawl.
            prepared_inputs (FetchWebPreparedInputs): Parameters from pre_execution.

        Returns:
            list[Path]: List of absolute paths to saved Markdown files.
        """
        output_path_base_for_target: Path = prepared_inputs["output_path_base_for_target"]
        max_depth_crawl_val: int = prepared_inputs["max_depth"]
        page_timeout_val: int = prepared_inputs["page_timeout_ms"]
        check_robots_val: bool = prepared_inputs["check_robots_txt"]
        saved_file_paths_abs: list[Path] = []

        self._log_info("Starting URL crawl for '%s' with max_depth: %d", target_value, max_depth_crawl_val)
        assert BFSDeepCrawlStrategy is not None and CrawlerRunConfig is not None
        strategy: Any = BFSDeepCrawlStrategy(max_depth=max_depth_crawl_val, include_external=False)
        run_config_deep_crawl_args: dict[str, Any] = {
            "deep_crawl_strategy": strategy,
            "page_timeout": page_timeout_val,
            "check_robots_txt": check_robots_val,
        }
        run_config_deep_crawl: Any = CrawlerRunConfig(**run_config_deep_crawl_args)

        results_list: list[Any] = await crawler.arun(url=target_value, config=run_config_deep_crawl)
        for result_item in results_list:
            saved_path: Optional[Path] = await self._save_markdown_from_result(result_item, output_path_base_for_target)
            if saved_path:
                saved_file_paths_abs.append(saved_path)
        return saved_file_paths_abs

    async def _handle_sitemap_target_async(
        self, crawler: Any, target_value: str, prepared_inputs: FetchWebPreparedInputs
    ) -> list[Path]:
        """Handle crawling for a 'sitemap' target type.

        Args:
            crawler (Any): The AsyncWebCrawler instance.
            target_value (str): The sitemap URL.
            prepared_inputs (FetchWebPreparedInputs): Parameters from pre_execution.

        Returns:
            list[Path]: List of absolute paths to saved Markdown files.
        """
        output_path_base_for_target: Path = prepared_inputs["output_path_base_for_target"]
        page_timeout_val: int = prepared_inputs["page_timeout_ms"]
        check_robots_val: bool = prepared_inputs["check_robots_txt"]
        assert CrawlerRunConfig is not None
        run_config_single_page_args: dict[str, Any] = {
            "page_timeout": page_timeout_val,
            "check_robots_txt": check_robots_val,
        }
        run_config_single_page: Any = CrawlerRunConfig(**run_config_single_page_args)
        return await self._crawl_sitemap_urls(
            crawler, target_value, output_path_base_for_target, run_config_single_page
        )

    async def _handle_file_target_async(
        self, crawler: Any, target_value: str, prepared_inputs: FetchWebPreparedInputs
    ) -> list[Path]:
        """Handle crawling for a 'file' target type (remote or local).

        Args:
            crawler (Any): The AsyncWebCrawler instance.
            target_value (str): The file URL or local path.
            prepared_inputs (FetchWebPreparedInputs): Parameters from pre_execution.

        Returns:
            list[Path]: List of absolute paths to saved Markdown files (usually one).
        """
        output_path_base_for_target: Path = prepared_inputs["output_path_base_for_target"]
        page_timeout_val: int = prepared_inputs["page_timeout_ms"]
        check_robots_val: bool = prepared_inputs["check_robots_txt"]
        saved_file_paths_abs: list[Path] = []
        assert CrawlerRunConfig is not None

        if target_value.startswith("http://") or target_value.startswith("https://"):
            self._log_info("Fetching remote file as single page: %s", target_value)
            run_config_single_page_args: dict[str, Any] = {
                "page_timeout": page_timeout_val,
                "check_robots_txt": check_robots_val,
            }
            run_config_single_page: Any = CrawlerRunConfig(**run_config_single_page_args)
            result_item_remote_file: Any = await crawler.arun(url=target_value, config=run_config_single_page)
            saved_path_remote: Optional[Path] = await self._save_markdown_from_result(
                result_item_remote_file, output_path_base_for_target, depth_override=0
            )
            if saved_path_remote:
                saved_file_paths_abs.append(saved_path_remote)
        else:
            self._log_info("Processing local file: %s", target_value)
            local_file_path: Path = Path(target_value)
            if local_file_path.is_file():
                try:
                    content: str = local_file_path.read_text(encoding="utf-8")
                    mock_crawl_result_dict: dict[str, Any] = {
                        "url": local_file_path.as_uri(),
                        "markdown": content,
                        "success": True,
                        "metadata": {"depth": 0},
                    }

                    class MockCrawlResult:
                        """A simple mock for CrawlResult for local file processing."""

                        def __init__(self, data: dict[str, Any]) -> None:
                            self.__dict__.update(data)

                    mock_crawl_result_obj = MockCrawlResult(mock_crawl_result_dict)
                    saved_md_path: Optional[Path] = await self._save_markdown_from_result(
                        mock_crawl_result_obj, output_path_base_for_target, depth_override=0
                    )
                    if saved_md_path:
                        saved_file_paths_abs.append(saved_md_path.resolve())
                except OSError as e_read_write:
                    self._log_error("Error reading/writing local file %s: %s", local_file_path, e_read_write)
            else:
                self._log_warning("Local file path '%s' not found or is not a file. Skipping.", target_value)
        return saved_file_paths_abs

    async def _execute_crawling_async(self, prepared_inputs: FetchWebPreparedInputs) -> FetchWebExecutionResult:
        """Asynchronous execution logic for crawling, supporting deep crawls for URL targets.

        Args:
            prepared_inputs (FetchWebPreparedInputs): Parameters from the pre_execution phase.

        Returns:
            FetchWebExecutionResult: A list of absolute paths to saved files, or None on failure.
        """
        if AsyncWebCrawler is None or BrowserConfig is None or CrawlerRunConfig is None or BFSDeepCrawlStrategy is None:
            self._log_error("Crawl4AI components are not available. Cannot execute crawl.")
            return None

        crawl_target: dict[str, Any] = prepared_inputs["crawl_target"]
        user_agent_str: str = prepared_inputs["user_agent"]
        saved_file_paths_abs: list[Path] = []

        assert BrowserConfig is not None and AsyncWebCrawler is not None
        browser_cfg: Any = BrowserConfig(headless=True, user_agent=user_agent_str, verbose=False)
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            target_type: Optional[str] = crawl_target.get("type")
            target_value: str = str(crawl_target.get("value"))

            if target_type == "url":
                saved_file_paths_abs = await self._handle_url_target_async(crawler, target_value, prepared_inputs)
            elif target_type == "sitemap":
                saved_file_paths_abs = await self._handle_sitemap_target_async(crawler, target_value, prepared_inputs)
            elif target_type == "file":
                saved_file_paths_abs = await self._handle_file_target_async(crawler, target_value, prepared_inputs)
            else:
                self._log_warning("Unknown crawl target type: %s", target_type)

        return [str(p) for p in saved_file_paths_abs]

    def execution(self, prepared_inputs: FetchWebPreparedInputs) -> FetchWebExecutionResult:
        """Execute web crawling based on prepared inputs.

        Args:
            prepared_inputs (FetchWebPreparedInputs): Parameters from the pre_execution phase.

        Returns:
            FetchWebExecutionResult: A list of absolute paths to saved files, or None on failure/skip.
        """
        if prepared_inputs.get("skip", True):
            reason_str: str = str(prepared_inputs.get("reason", "N/A"))
            self._log_info("Skipping web page fetching execution. Reason: %s", reason_str)
            return None

        self._log_info("Executing web page fetching...")
        output_path_base_target: Path = prepared_inputs["output_path_base_for_target"]
        try:
            output_path_base_target.mkdir(parents=True, exist_ok=True)
            self._log_info("Ensured output directory for target exists: %s", output_path_base_target.resolve())
        except OSError as e_dir:
            self._log_error(
                "Failed to create target output directory %s: %s. Cannot save crawled files.",
                output_path_base_target,
                e_dir,
            )
            return None

        try:
            return asyncio.run(self._execute_crawling_async(prepared_inputs))
        except (IOError, OSError, AttributeError, TypeError, ValueError) as e:
            self._log_error("Error during asynchronous web crawling execution: %s", e, exc_info=True)
        except RuntimeError as e_rt:
            self._log_error(
                "RuntimeError during asyncio execution (possibly nested event loops): %s. ",
                e_rt,
                exc_info=True,
            )
        return None

    def _handle_llm_extended_processing(
        self, shared_context: SLSharedContext, saved_files_abs_paths: list[str], intended_output_dir_abs: Path
    ) -> None:
        """Populate `shared_context["files"]` for "llm_extended" mode.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.
            saved_files_abs_paths (list[str]): List of absolute paths to saved crawled files.
            intended_output_dir_abs (Path): The absolute base directory where crawled files were saved.
        """
        self._log_info("LLM_EXTENDED mode: Populating shared_context['files'] with crawled content.")
        files_for_pipeline: "FilePathContentList" = []
        abs_intended_output_dir: Path = intended_output_dir_abs.resolve()

        for file_path_str in saved_files_abs_paths:
            try:
                file_path_abs: Path = Path(file_path_str).resolve()
                if not file_path_abs.is_file():
                    self._log_warning("File %s not found or is not a file. Skipping for pipeline.", file_path_abs)
                    continue

                relative_path_for_context: Path = file_path_abs.relative_to(abs_intended_output_dir)
                content: str = file_path_abs.read_text(encoding="utf-8")
                files_for_pipeline.append((relative_path_for_context.as_posix(), content))
                self._log_debug("Added to pipeline: '%s'", relative_path_for_context.as_posix())
            except (OSError, ValueError, TypeError) as e_read:
                self._log_error("Failed to read/process crawled file %s for pipeline: %s", file_path_str, e_read)
        shared_context["files"] = files_for_pipeline
        self._log_info("Added %d crawled files to shared_context['files'] for LLM processing.", len(files_for_pipeline))

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: FetchWebPreparedInputs,
        execution_outputs: FetchWebExecutionResult,
    ) -> None:
        """Store paths of saved files and conditionally populate `shared_context["files"]`.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.
            prepared_inputs (FetchWebPreparedInputs): Parameters from pre_execution.
            execution_outputs (FetchWebExecutionResult): List of saved file paths, or None.
        """
        intended_output_dir_str_any: Any = shared_context.get("final_output_dir_web_crawl")
        intended_output_dir_abs: Optional[Path] = (
            Path(str(intended_output_dir_str_any)).resolve() if intended_output_dir_str_any else None
        )

        if prepared_inputs.get("skip", True):
            self._log_info("Web page fetching was skipped. No files processed.")
            shared_context.setdefault("files", [])
            if intended_output_dir_abs:
                self._log_info("Intended output directory (skipped): %s", intended_output_dir_abs)
            return

        saved_files_abs_paths: list[str] = [str(p) for p in (execution_outputs or []) if isinstance(p, (str, Path))]

        if saved_files_abs_paths:
            self._log_info("Successfully fetched and saved %d web pages/files.", len(saved_files_abs_paths))
            if intended_output_dir_abs and intended_output_dir_abs.exists() and intended_output_dir_abs.is_dir():
                shared_context["final_output_dir_web_crawl"] = str(intended_output_dir_abs)
                self._log_info("Confirmed output directory for saved raw files: %s", intended_output_dir_abs)

                processing_mode: str = str(prepared_inputs.get("processing_mode", "minimalistic"))
                self._log_info(
                    "FetchWebPage post_execution: Processing_mode from prepared_inputs: '%s'", processing_mode
                )
                if processing_mode == "llm_extended":
                    self._handle_llm_extended_processing(shared_context, saved_files_abs_paths, intended_output_dir_abs)
                else:
                    shared_context["files"] = []
                    self._log_info(
                        "Minimalistic mode: shared_context['files'] intentionally not populated for LLM pipeline."
                    )
            else:
                self._log_warning(
                    "Files reported as saved, but target directory '%s' not found or not a directory.",
                    intended_output_dir_abs,
                )
                shared_context["files"] = []
        elif execution_outputs is not None:
            self._log_warning("Web page fetching executed but no files were saved.")
            shared_context["files"] = []
            if intended_output_dir_abs:
                self._log_info("Target output directory (no files saved): %s", intended_output_dir_abs)
        else:
            self._log_error("Web page fetching execution failed. Check previous logs for errors.")
            shared_context["files"] = []
            if intended_output_dir_abs:
                self._log_info("Target output directory (execution failed): %s", intended_output_dir_abs)


# End of src/FL02_web_crawling/nodes/n01_fetch_web_page.py
