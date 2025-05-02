```toml
# Content of pyproject.toml (derived from context)

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sourcelens"
version = "0.1.0" # Assuming version from src/sourcelens/__init__.py
description = "AI-powered tool to generate tutorials from codebases."
readme = "README.md"
license = { file = "LICENSE" } # Or text = "MIT" / "GPL-3.0-or-later" depending on LICENSE file
authors = [
    { name = "Your Name", email = "your.email@example.com" }, # Placeholder - Replace!
]
keywords = ["ai", "llm", "code-analysis", "tutorial-generator", "documentation", "markdown"]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "License :: OSI Approved :: MIT License", # Adjust if license is different (e.g., GNU GPL v3)
    "Operating System :: OS Independent",
    "Topic :: Software Development :: Documentation",
    "Topic :: Utilities",
    "Environment :: Console",
    "Intended Audience :: Developers",
]

dependencies = [
    # Core runtime dependencies inferred from requirements.txt and imports
    "pocketflow>=0.0.1",
    "PyYAML>=6.0",
    "requests>=2.28.0",
    "GitPython>=3.1.0",
    "google-cloud-aiplatform>=1.25.0", # Check if strictly needed or only for vertexai
    "google-generativeai>=0.8.0",
    "jsonschema>=4.0.0",
    # Add others if needed (e.g., anthropic, openai SDKs if used directly)
]

[project.optional-dependencies]
dev = [
    # Dependencies for development: testing, linting, type checking
    "pytest>=7.0",
    "pytest-cov>=4.0", # For coverage reporting
    "ruff>=0.1.0",     # Fast linter and formatter
    "mypy>=1.0",       # Static type checker
    "types-PyYAML",    # Type hints for PyYAML
    "types-requests",  # Type hints for requests
    # Add others like types-setuptools if needed
]

[project.scripts]
sourcelens = "sourcelens.main:main" # Defines the command-line entry point

# Tool specific configurations
[tool.setuptools]
packages = { find = { where = ["src"] } }
package-dir = { "" = "src" }

[tool.ruff]
line-length = 100
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes errors
    "I",  # isort import sorting
    "C",  # mccabe complexity
    "B",  # flake8-bugbear opinionated warnings
    "A",  # flake8-builtins
    "COM",# flake8-commas
    "D",  # pydocstyle docstrings (can be noisy initially)
    "UP", # pyupgrade syntax upgrades
    "PTH",# flake8-use-pathlib
    "SIM",# flake8-simplify
    "TID",# flake8-tidy-imports
    "ARG",# flake8-unused-arguments
    "PL", # Pylint rules ported to ruff
    "TRY",# tryceratops exception handling
    "RUF",# Ruff-specific rules
]
ignore = [
    "E501", # Line too long (handled by formatter, but sometimes needed)
    "B008", # Function call argument default depends on mutable value (sometimes intentional)
    "D100", # Missing docstring in public module
    "D104", # Missing docstring in public package
    "D107", # Missing docstring in __init__
    "TRY003", # Avoid specifying long messages outside the exception class
    "PLR2004", # Magic value used in comparison (sometimes acceptable for constants)
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"] # Ignore unused imports in init files
"tests/*" = ["D100", "D101", "D102", "D103", "S101"] # Relax docstrings, allow 'assert' in tests

[tool.mypy]
python_version = "3.10" # Target version for checking
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
strict = true # Enable stricter checking
packages = ["sourcelens"] # Specify the package to check

[[tool.mypy.overrides]]
module = [
    "git.*", # Ignore missing type hints for GitPython
    "google.generativeai.*", # Ignore potential missing type hints for SDK
    "google.cloud.aiplatform.*",
    "pocketflow.*", # Ignore missing type hints if library doesn't provide them
    "jsonschema.*",
]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "6.0"
addopts = "-ra -q --cov=sourcelens --cov-report=term-missing --no-cov-on-fail" # Report reasons, quiet, add coverage
testpaths = [
    "tests",
]

[tool.coverage.run]
source = ["sourcelens"]
branch = true
omit = [
    "*/__init__.py",
    "*/_exceptions.py", # Often simple, no logic to test coverage
    "tests/*",
    "src/sourcelens/main.py", # Often harder to unit test CLI setup directly
]

[tool.coverage.report]
fail_under = 80 # Example: Fail build if coverage drops below 80%
show_missing = true
```

---

Now, here is the explanation formatted into `how_to_pyproject_toml.md`:

```markdown
# Understanding pyproject.toml in sourceLens

The `pyproject.toml` file is the central configuration file for modern Python projects, including `sourceLens`. It defines project metadata, dependencies, build instructions, and settings for various development tools. This document explains the key sections found in the `sourceLens` `pyproject.toml`.

## 1. `[build-system]`

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
```

*   **Purpose:** Tells Python packaging tools (like `pip`) *how* to build the project.
*   `requires`: Specifies packages needed *during the build process* itself (usually `setuptools` and `wheel`).
*   `build-backend`: Points to the function used by the build system (`setuptools` in this case) to create distributable packages (like wheels).

## 2. `[project]` (PEP 621 Metadata)

This is the standard section for defining core project information.

```toml
[project]
name = "sourcelens"
version = "0.1.0"
description = "AI-powered tool to generate tutorials from codebases."
readme = "README.md"
license = { file = "LICENSE" }
authors = [ ... ]
keywords = [ ... ]
classifiers = [ ... ]
```

*   `name`: The official package name used for installation (`pip install sourcelens`).
*   `version`: The current version of the package. Should be updated for new releases.
*   `description`: A short summary displayed on package indices like PyPI.
*   `readme`: Specifies the file containing the long description (usually `README.md`).
*   `license`: Declares the project's license (points to the `LICENSE` file).
*   `authors`, `keywords`, `classifiers`: Standard metadata for contact info, searchability, and categorization on PyPI.

### 2.1 Dependencies

```toml
dependencies = [
    "pocketflow>=0.0.1",
    "PyYAML>=6.0",
    "requests>=2.28.0",
    # ... other runtime dependencies
]
```

*   Lists the packages required for `sourceLens` to *run* after installation. These are automatically installed when a user runs `pip install sourcelens`.

### 2.2 Optional Dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "mypy>=1.0",
    # ... other development tools
]
```

*   Defines sets of dependencies that are not required for basic runtime but are useful for specific purposes, like development.
*   The `dev` group includes tools for testing (`pytest`, `pytest-cov`), linting/formatting (`ruff`), and static type checking (`mypy`).
*   These can be installed using `pip install .[dev]` (the `.` installs the current project).

### 2.3 Scripts (Command-Line Entry Point)

```toml
[project.scripts]
sourcelens = "sourcelens.main:main"
```

*   **Crucial:** This defines the command-line interface command.
*   It maps the command name (`sourcelens`) to a specific function (`main`) within a module (`sourcelens.main`).
*   When the package is installed, `pip` creates an executable script that runs this specified function, allowing users to simply type `sourcelens` in their terminal (within the activated virtual environment).

## 3. `[tool.setuptools]`

```toml
[tool.setuptools]
packages = { find = { where = ["src"] } }
package-dir = { "" = "src" }
```

*   Configuration specific to the `setuptools` build backend.
*   `package-dir = { "" = "src" }`: Tells `setuptools` that the source code resides in the `src` directory, not directly in the root.
*   `packages = { find = { where = ["src"] } }`: Instructs `setuptools` to automatically find all packages within the `src` directory to include in the distribution.

## 4. `[tool.*]` (Development Tool Configurations)

These sections configure various linters, formatters, type checkers, and testing tools to ensure code quality and consistency.

*   **`[tool.ruff]`:** Configures Ruff, a fast Python linter and formatter.
    *   `line-length`: Sets the maximum line length allowed.
    *   `select`: Enables specific categories or individual rules to check for.
    *   `ignore`: Disables specific rules that might conflict or be too noisy.
    *   `per-file-ignores`: Allows disabling rules only for specific files/patterns.
*   **`[tool.mypy]`:** Configures MyPy, the static type checker.
    *   `python_version`: Sets the target Python version for type analysis.
    *   `strict`: Enables stricter type checking rules.
    *   `packages`: Specifies which package(s) MyPy should analyze.
    *   `overrides`: Allows ignoring missing type hints (`ignore_missing_imports = true`) for specific libraries that may not provide them.
*   **`[tool.pytest.ini_options]`:** Configures Pytest, the testing framework.
    *   `addopts`: Sets default command-line options passed to `pytest` (e.g., enabling coverage).
    *   `testpaths`: Specifies where Pytest should look for test files.
*   **`[tool.coverage.run]` & `[tool.coverage.report]`:** Configures Coverage.py, used to measure test coverage.
    *   `source`: Specifies the code to measure coverage against.
    *   `omit`: Excludes certain files (like `__init__` files or tests themselves) from coverage reports.
    *   `fail_under`: (Optional) Sets a minimum coverage percentage required for builds to pass.

## 5. Mermaid Diagram Support (Viewing Output)

`sourceLens` generates relationship diagrams using the [Mermaid](https://mermaid.js.org/) syntax within its Markdown output files (e.g., `index.md`).

*   **Viewing:** To see these diagrams rendered visually:
    *   **VS Code:** Install the **"Markdown Preview Mermaid Support"** extension from the Visual Studio Code Marketplace. Once installed and enabled, Mermaid diagrams should automatically render in the standard Markdown preview (`Ctrl+Shift+V` or `Cmd+Shift+V`).
    *   **GitHub/GitLab:** These platforms render Mermaid diagrams in Markdown files automatically.
    *   **Other Editors/Viewers:** Check if your Markdown editor or viewer has built-in Mermaid support or requires a specific plugin.

## Conclusion

The `pyproject.toml` file is fundamental to the `sourceLens` project. It centralizes project definition, dependency management, build configuration, and development tooling settings, promoting consistency and making the project easier to build, install, and contribute to.
```