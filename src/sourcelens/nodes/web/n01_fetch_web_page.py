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
LLM-optimized text files from the web, converting them to Markdown,
and saving them to a specified output subdirectory.
It serves as an alternative entry point to the SourceLens pipeline
for web-based content.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Final, Optional
from urllib.parse import urlparse

from typing_extensions import TypeAlias

# Corrected import path for BaseNode and SLSharedContext
from sourcelens.nodes.base_node import BaseNode, SLSharedContext
from sourcelens.utils.helpers import sanitize_filename

_module_logger_fetchweb = logging.getLogger(__name__)

CRAWL4AI_AVAILABLE: bool = False
AsyncWebCrawler: Optional[Any] = None
BrowserConfig: Optional[Any] = None
CrawlResult: Optional[Any] = None
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
        CrawlResult as ImportedCrawlResultC4AI,
    )

    AsyncWebCrawler = ImportedAsyncWebCrawlerC4AI
    BrowserConfig = ImportedBrowserConfigC4AI
    CrawlResult = ImportedCrawlResultC4AI

    _module_logger_fetchweb.info("Core Crawl4AI components imported successfully.")
    CRAWL4AI_AVAILABLE = True
except ImportError as e_import_crawl:
    failed_module_name = (
        e_import_crawl.name if hasattr(e_import_crawl, "name") and e_import_crawl.name else "a Crawl4AI dependency"
    )
    _module_logger_fetchweb.error(
        "Failed to import %s: %s. Web crawling functionality will be disabled.", failed_module_name, e_import_crawl
    )
    CRAWL4AI_AVAILABLE = False


# Type Aliases
FetchWebPreparedInputs: TypeAlias = dict[str, Any]
FetchWebExecutionResult: TypeAlias = Optional[list[str]]  # List of paths to saved markdown files

# Constants
DEFAULT_LOCAL_OUTPUT_DIR: Final[str] = "output"
DEFAULT_WEB_OUTPUT_SUBDIR: Final[str] = "crawled_web_pages"
DEFAULT_MAX_DEPTH: Final[int] = 1
SITEMAP_NAMESPACES: Final[dict[str, str]] = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
MAX_DOMAIN_PATH_LEN_FOR_SUBDIR: Final[int] = 50


class FetchWebPage(BaseNode[FetchWebPreparedInputs, FetchWebExecutionResult]):
    """Fetches web content, converts to Markdown, and saves it locally."""

    def __init__(self, max_retries: int = 1, wait: int = 5) -> None:
        """Initialize the FetchWebPage node.

        Args:
            max_retries (int): Max retries for fetching a single URL.
            wait (int): Wait time between retries in seconds.
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
        """Prepare parameters for web crawling.

        Sets up paths and configurations. If Crawl4AI is not available or no
        target is specified, it prepares to skip execution.

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

        crawl_target = self._get_crawl_target(shared_context)
        if not crawl_target:
            self._log_info("No web crawl target specified. Skipping web fetch.")
            return {"skip": True, "reason": "No web crawl target specified."}

        config_val: Any = shared_context.get("config", {})
        config: dict[str, Any] = config_val if isinstance(config_val, dict) else {}

        web_opts_val: Any = config.get("web_crawler_options", {})
        web_opts: dict[str, Any] = web_opts_val if isinstance(web_opts_val, dict) else {}

        output_config_val: Any = config.get("output", {})
        output_config: dict[str, Any] = output_config_val if isinstance(output_config_val, dict) else {}

        base_output_dir_str: str = str(output_config.get("base_dir", DEFAULT_LOCAL_OUTPUT_DIR))
        cli_subdir_override: Optional[Any] = shared_context.get("cli_crawl_output_subdir")
        default_web_content_subdir: str = (
            str(cli_subdir_override)
            if cli_subdir_override and isinstance(cli_subdir_override, str)
            else str(web_opts.get("default_output_subdir_name", DEFAULT_WEB_OUTPUT_SUBDIR))
        )

        crawl_target_value_str = str(crawl_target["value"])
        parsed_url_target = urlparse(crawl_target_value_str)
        domain_name_target = parsed_url_target.netloc or "local_file_or_unknown"
        path_name_target = parsed_url_target.path.strip("/").replace("/", "_") or "index"
        raw_target_name_for_dir = f"{domain_name_target}_{path_name_target}"

        specific_target_subdir_name_raw = sanitize_filename(raw_target_name_for_dir)
        specific_target_subdir_name_domain = sanitize_filename(domain_name_target)

        specific_target_subdir_name = (
            specific_target_subdir_name_raw[:MAX_DOMAIN_PATH_LEN_FOR_SUBDIR]
            or specific_target_subdir_name_domain[:MAX_DOMAIN_PATH_LEN_FOR_SUBDIR]
            or "crawled_site"
        )

        output_path_for_target = Path(base_output_dir_str) / default_web_content_subdir / specific_target_subdir_name
        shared_context["final_output_dir_web_crawl"] = str(output_path_for_target.resolve())
        self._log_info("Target output directory for this crawl: %s", output_path_for_target.resolve())

        cli_depth_override_val: Any = shared_context.get("cli_crawl_depth")
        max_depth_from_config = int(web_opts.get("max_depth_recursive", DEFAULT_MAX_DEPTH))
        max_depth_val = (
            int(cli_depth_override_val) if isinstance(cli_depth_override_val, int) else max_depth_from_config
        )

        processing_mode_val: Any = web_opts.get("processing_mode", "minimalistic")
        processing_mode: str = str(processing_mode_val)

        return {
            "skip": False,
            "crawl_target": crawl_target,
            "output_path_base_for_target": output_path_for_target,
            "max_depth": max_depth_val,
            "user_agent": str(web_opts.get("user_agent", "SourceLensBot/0.1 (sourcelens-project)")),
            "processing_mode": processing_mode,
        }

    async def _fetch_and_save_url(self, crawler: Any, url: str, output_path_base: Path) -> Optional[Path]:
        """Fetch a single URL asynchronously and save its Markdown content.

        Args:
            crawler (Any): An instance of `crawl4ai.AsyncWebCrawler`.
            url (str): The URL to fetch.
            output_path_base (Path): The base directory for saving the file.

        Returns:
            Optional[Path]: The absolute path to the saved file if successful, else None.
        """
        self._log_info("Crawling URL: %s", url)
        if crawler is None:
            self._log_error("AsyncWebCrawler component not available for fetching URL.")
            return None
        try:
            result: Any = await crawler.arun(url=url)
            if hasattr(result, "success") and result.success and hasattr(result, "markdown") and result.markdown:
                parsed_url = urlparse(url)
                path_segments = [seg for seg in parsed_url.path.strip("/").split("/") if seg]

                if path_segments:
                    base_filename_part = path_segments[-1]
                elif parsed_url.netloc:
                    base_filename_part = parsed_url.netloc
                else:
                    base_filename_part = Path(parsed_url.path).stem or "content"

                base_filename_sanitized = sanitize_filename(base_filename_part)[:100] or "page"
                if parsed_url.netloc and parsed_url.netloc not in base_filename_part:
                    domain_prefix = sanitize_filename(parsed_url.netloc)[:30]
                    final_filename_base = f"{domain_prefix}_{base_filename_sanitized}"
                else:
                    final_filename_base = base_filename_sanitized
                final_filename_base = final_filename_base[:120]

                abs_output_path_base = output_path_base.resolve()
                filepath = abs_output_path_base / f"{final_filename_base}.md"
                try:
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    filepath.write_text(result.markdown, encoding="utf-8")
                    self._log_info("Saved Markdown for %s to %s", url, filepath)
                    return filepath.resolve()
                except OSError as e_write:
                    self._log_error("Failed to write file %s: %s", filepath, e_write)

            elif (
                hasattr(result, "success")
                and result.success
                and (not hasattr(result, "markdown") or not result.markdown)
            ):
                self._log_warning("Successfully crawled %s but no Markdown content extracted.", url)
            elif hasattr(result, "error_message"):
                self._log_error("Failed to crawl %s: %s", url, result.error_message)
            else:
                self._log_error("Failed to crawl %s: Unknown error or unexpected result structure.", url)

        except (IOError, OSError, AttributeError, TypeError, ValueError) as e:
            self._log_error("Error processing URL %s: %s", url, e, exc_info=True)
        return None

    async def _crawl_recursively(
        self, crawler: Any, start_url: str, max_depth_param: int, output_path_base: Path
    ) -> list[Path]:
        """Perform recursive crawling (simplified version).

        Args:
            crawler (Any): An instance of `crawl4ai.AsyncWebCrawler`.
            start_url (str): The URL to start crawling from.
            max_depth_param (int): The maximum depth for recursive crawling.
            output_path_base (Path): The base directory for saving files.

        Returns:
            list[Path]: A list of absolute paths to successfully saved files.
        """
        self._log_info("Starting recursive crawl from %s, max_depth: %d", start_url, max_depth_param)
        saved_files: list[Path] = []
        if max_depth_param >= 0:
            path_result = await self._fetch_and_save_url(crawler, start_url, output_path_base)
            if path_result:
                saved_files.append(path_result)
        self._log_warning(
            "Recursive crawling is simplified and currently only processes the start_url. "
            "Full recursive discovery not yet implemented."
        )
        return saved_files

    async def _crawl_sitemap(self, crawler: Any, sitemap_url: str, output_path_base: Path) -> list[Path]:
        """Fetch URLs from sitemap and crawl them asynchronously.

        Args:
            crawler (Any): An instance of `crawl4ai.AsyncWebCrawler`.
            sitemap_url (str): The URL of the sitemap.xml.
            output_path_base (Path): The base directory for saving files.

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

            response = requests_module.get(sitemap_url, timeout=30)
            response.raise_for_status()
            root = ElementTree_module.fromstring(response.content)
            urls_from_sitemap = [loc.text for loc in root.findall(".//ns:loc", SITEMAP_NAMESPACES) if loc.text]
            self._log_info("Found %d URLs in sitemap. Crawling...", len(urls_from_sitemap))

            saved_files: list[Path] = []
            tasks = [self._fetch_and_save_url(crawler, url, output_path_base) for url in urls_from_sitemap]
            results: list[Optional[Path]] = await asyncio.gather(*tasks)
            for path_result in results:
                if path_result:
                    saved_files.append(path_result)
            return saved_files
        except requests_module.RequestException as e:
            self._log_error("Failed to fetch sitemap %s: %s", sitemap_url, e)
        except ElementTree_module.ParseError as e:
            self._log_error("Failed to parse XML from sitemap %s: %s", sitemap_url, e)
        except AttributeError as e_attr:
            self._log_error("XML ElementTree components not available, cannot parse sitemap: %s", e_attr)
        return []

    async def _execute_crawling_async(self, prepared_inputs: FetchWebPreparedInputs) -> FetchWebExecutionResult:
        """Asynchronous execution logic for crawling.

        Args:
            prepared_inputs (FetchWebPreparedInputs): Parameters from the pre_execution phase.

        Returns:
            FetchWebExecutionResult: A list of absolute paths to saved files, or None on failure.
        """
        if AsyncWebCrawler is None or BrowserConfig is None:
            self._log_error("Crawl4AI components (AsyncWebCrawler, BrowserConfig) are not available.")
            return None

        crawl_target: dict[str, Any] = prepared_inputs["crawl_target"]
        output_path_base_for_target: Path = prepared_inputs["output_path_base_for_target"]
        user_agent: str = prepared_inputs["user_agent"]
        max_depth_crawl: int = prepared_inputs["max_depth"]

        browser_cfg = BrowserConfig(headless=True, user_agent=user_agent, verbose=False)
        saved_file_paths_abs: list[Path] = []

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            target_type = crawl_target.get("type")
            target_value = str(crawl_target.get("value"))

            if target_type == "url":
                if max_depth_crawl > 0:
                    paths = await self._crawl_recursively(
                        crawler, target_value, max_depth_crawl, output_path_base_for_target
                    )
                    saved_file_paths_abs.extend(paths)
                else:
                    path_result = await self._fetch_and_save_url(crawler, target_value, output_path_base_for_target)
                    if path_result:
                        saved_file_paths_abs.append(path_result)
            elif target_type == "sitemap":
                paths = await self._crawl_sitemap(crawler, target_value, output_path_base_for_target)
                saved_file_paths_abs.extend(paths)
            elif target_type == "file":
                if target_value.startswith("http://") or target_value.startswith("https://"):
                    path_result = await self._fetch_and_save_url(crawler, target_value, output_path_base_for_target)
                    if path_result:
                        saved_file_paths_abs.append(path_result)
                else:
                    self._log_warning(
                        "Local file path '%s' provided to web crawler. This node is for web URLs. Skipping.",
                        target_value,
                    )
        return [str(p) for p in saved_file_paths_abs]

    def execution(self, prepared_inputs: FetchWebPreparedInputs) -> FetchWebExecutionResult:
        """Execute web crawling based on prepared inputs.

        Ensures the output directory exists and runs the asynchronous crawling logic.

        Args:
            prepared_inputs (FetchWebPreparedInputs): Parameters from the pre_execution phase.

        Returns:
            FetchWebExecutionResult: A list of absolute paths to saved files, or None on failure.
        """
        if prepared_inputs.get("skip", True):
            reason = str(prepared_inputs.get("reason", "N/A"))
            self._log_info("Skipping web page fetching execution. Reason: %s", reason)
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
            self._log_error("RuntimeError during asyncio execution: %s", e_rt, exc_info=True)
        return None

    def _handle_llm_extended_processing(
        self, shared_context: SLSharedContext, saved_files_abs_paths: list[str], intended_output_dir_abs: Path
    ) -> None:
        """Handle the 'llm_extended' processing mode.

        Reads crawled files and populates shared_context["files"] for further LLM pipeline processing.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.
            saved_files_abs_paths (list[str]): List of absolute paths to successfully saved crawled files.
            intended_output_dir_abs (Path): The absolute base directory where crawled files were saved.
        """
        self._log_info("LLM_EXTENDED mode: Populating shared_context['files'] with crawled content.")
        files_for_pipeline: list[tuple[str, str]] = []
        abs_intended_output_dir = intended_output_dir_abs.resolve()

        for file_path_str in saved_files_abs_paths:
            try:
                file_path_abs = Path(file_path_str).resolve()
                if not file_path_abs.is_file():
                    self._log_warning("File %s not found or is not a file. Skipping for pipeline.", file_path_abs)
                    continue

                relative_path_for_context = file_path_abs.relative_to(abs_intended_output_dir)
                content = file_path_abs.read_text(encoding="utf-8")
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
        intended_output_dir_str = shared_context.get("final_output_dir_web_crawl")
        intended_output_dir_abs: Optional[Path] = (
            Path(str(intended_output_dir_str)).resolve() if intended_output_dir_str else None
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
                shared_context["final_output_dir"] = str(intended_output_dir_abs)
                self._log_info("Confirmed output directory for saved files: %s", intended_output_dir_abs)
                processing_mode: str = str(prepared_inputs.get("processing_mode", "minimalistic"))
                if processing_mode == "llm_extended":
                    self._handle_llm_extended_processing(shared_context, saved_files_abs_paths, intended_output_dir_abs)
                else:
                    shared_context.setdefault("files", [])
            else:
                self._log_warning(
                    "Files reported as saved, but target directory '%s' not found or not a directory.",
                    intended_output_dir_abs,
                )
        elif execution_outputs is not None:
            self._log_warning("Web page fetching executed but no files were saved.")
            if intended_output_dir_abs:
                self._log_info("Target output directory (no files saved): %s", intended_output_dir_abs)
        else:
            self._log_error("Web page fetching execution failed. Check previous logs for errors.")
            if intended_output_dir_abs:
                self._log_info("Target output directory (execution failed): %s", intended_output_dir_abs)


# End of src/sourcelens/nodes/web/n01_fetch_web_page.py
