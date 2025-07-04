## Installation

**Prerequisites:**

*   Python 3.9 or higher
*   Git (for code analysis from repositories)

**Steps:**

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/openXFlow/sourceLensAI.git
    cd sourceLensAI
    ```

2.  **Set up a Virtual Environment (Recommended):**
    *   Linux/macOS: `python3 -m venv venv && source venv/bin/activate`
    *   Windows: `python -m venv venv && .\venv\Scripts\activate`
    *(Your command prompt should now show `(venv)` prefix)*

3.  **Install Dependencies:**
    *   For core functionality and all features (code & web analysis, development tools):
        ```bash
        pip install -e .[all,dev]
        ```
    *   If you only need code analysis: `pip install -e .[code_analysis,dev]`
    *   If you only need web content analysis: `pip install -e .[web_crawling,dev]`
    *   **Playwright Browsers (for Web Crawling):** The `crawl4ai` library (a dependency for web crawling) uses Playwright. You'll need to install its browser drivers:
        ```bash
        playwright install # Installs default browsers
        # or playwright install chromium # For a specific browser
        ```

