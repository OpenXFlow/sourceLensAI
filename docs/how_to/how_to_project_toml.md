# Understanding `pyproject.toml` in SourceLens

The `pyproject.toml` file is the central configuration file for the `sourceLens` project, adhering to modern Python packaging standards (PEP 621). It defines project metadata, dependencies, build instructions, and settings for development tools. This guide breaks down each key section.

## 1. `[build-system]`

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

*   **Purpose:** This section tells tools like `pip` and `build` *how to build the project*.
*   **`requires`**: Lists packages needed *during the build process itself*. For `sourceLens`, this is `setuptools`.
*   **`build-backend`**: Specifies the function within the build system that will be called to create distributable packages (e.g., wheels).

## 2. `[project]` - Core Project Metadata

This section contains all the essential information about the `sourceLens` package.

```toml
[project]
name = "sourcelens"
version = "0.2.0"
description = "AI-powered tool to generate tutorials from source code or web content."
readme = "README.md"
authors = [ { name = "Jozef Darida", email = "darijo2@yahoo.com" } ]
license = { text = "GPL-3.0-or-later" }
requires-python = ">=3.9"
classifiers = [ ... ]
```

*   **`name`**: The official package name for installation (`pip install sourcelens`).
*   **`version`**: The current package version. This **must** be kept in sync with `src/sourcelens/__init__.py`.
*   **`description`**: A short summary shown on package indexes like PyPI.
*   **`readme`**: Points to the file used for the long description on PyPI.
*   **`license`**: Declares the project's license.
*   **`authors`**: Contact information for the project authors.
*   **`classifiers`**: Standardized strings that categorize the project on PyPI, helping users find it.

### 2.1. Dependencies

#### Runtime Dependencies
```toml
[project]
dependencies = [
    "PyYAML>=6.0",
    "attrs>=21.3.0",
    # ... other core dependencies
]
```
This list defines the packages that are **essential for `sourceLens` to run**. They are automatically installed when a user runs `pip install sourcelens`.

#### Optional Dependencies
```toml
[project.optional-dependencies]
code_analysis = [ "GitPython>=3.1.0" ]
web_crawling = [ "crawl4ai>=0.6.3", "yt-dlp>=2023.12.30", ... ]
all = [ "sourcelens[code_analysis]", "sourcelens[web_crawling]" ]
dev = [ "pytest>=7.0", "ruff>=0.1.0", "mypy>=1.0", ... ]
```
This section defines "extras," which are sets of dependencies for specific functionalities:
*   **`code_analysis` & `web_crawling`**: These contain dependencies needed only for their respective flows. This allows users to install a minimal version if they only need one type of analysis (e.g., `pip install sourcelens[web_crawling]`).
*   **`all`**: A convenience extra to install all functional dependencies.
*   **`dev`**: Contains tools for development, such as testing (`pytest`), linting (`ruff`), and type checking (`mypy`). These are installed using `pip install .[dev]`.

### 2.2. URLs & Scripts

```toml
[project.urls]
Homepage = "https://github.com/OpenXFlow/sourceLensAI"
Repository = "https://github.com/OpenXFlow/sourceLensAI"

[project.scripts]
sourcelens = "sourcelens.main:main"
```
*   **`[project.urls]`**: Provides helpful links that appear on the PyPI project page.
*   **`[project.scripts]`**: **This is crucial.** It creates the command-line entry point. It maps the command `sourcelens` to the `main` function inside the `sourcelens.main` module, making the tool executable from the terminal after installation.

## 3. `[tool.setuptools]` - Build Configuration

```toml
[tool.setuptools.packages.find]
where = ["src"]
```
This section configures the `setuptools` build backend. It tells `setuptools` to find all Python packages to include in the distribution inside the `src/` directory. This is standard practice for a `src`-layout project structure.

## 4. `[tool.*]` - Developer Tooling

These sections configure tools used for maintaining code quality and consistency.

*   **`[tool.ruff]`**: Configures **Ruff**, an extremely fast Python linter and formatter.
    *   `line-length`: Sets the maximum line length.
    *   `select`: A list of rule codes to enable (e.g., `E` for pycodestyle errors, `D` for pydocstyle).
    *   `ignore`: A list of rule codes to disable project-wide.
    *   `lint.pydocstyle.convention`: Specifies the expected docstring style (e.g., `google`).
*   **`[tool.mypy]`**: Configures **MyPy**, the static type checker.
    *   `python_version`: The target Python version for type analysis.
    *   `packages`: Specifies which packages MyPy should analyze.
    *   `[[tool.mypy.overrides]]`: A crucial section that tells MyPy to ignore missing type information for third-party libraries (like `yt_dlp` or `crawl4ai`) that do not ship with type hints. This prevents false-positive errors during type checking.

