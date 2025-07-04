
# How to Build and Distribute the `sourceLens` Package

This guide provides comprehensive instructions for building distributable packages (wheels and source distributions) for the `sourceLens` project. These packages allow for easy installation via `pip`, which is the standard for deployment and sharing.

## 1. Prerequisites Checklist

Before you begin, ensure you have the following in place:

*   [ ] **Python 3.9+ and `pip`:** Your development environment must have a compatible version of Python and `pip`.
*   [ ] **Virtual Environment:** You should be working inside the project's activated virtual environment to ensure dependency isolation.
*   [ ] **`build` Package:** The modern `build` frontend must be installed. If you haven't installed it yet, run:
    ```bash
    pip install build
    ```
*   [ ] **Updated `pyproject.toml`:** This file is the heart of the package configuration. Verify that all metadata is accurate, especially:
    *   `name`, `description`, `authors`, `license`.
    *   All runtime dependencies are correctly listed under `[project.dependencies]`.
*   [ ] **Synchronized Version Number:** The `version` in `pyproject.toml` **must** match the `__version__` variable in `src/sourcelens/__init__.py`. Keeping these synchronized is critical for package consistency.

    **Example `pyproject.toml`:**
    ```toml
    [project]
    name = "sourcelens"
    version = "0.2.0" 
    ...
    ```

    **Example `src/sourcelens/__init__.py`:**
    ```python
    __version__ = "0.2.0"
    ```

## 2. The Build Process

The process involves two main steps: cleaning the workspace and running the build command.

### Step 1: Clean Previous Builds (Recommended)

To prevent any old files from being included in your new package, it's best to remove artifacts from previous builds.

From the project root directory (`sourceLens/`), run:

```bash
# On Linux/macOS
rm -rf build/ dist/ src/sourcelens.egg-info/

# On Windows (PowerShell)
Remove-Item -Recurse -Force build, dist, src/sourcelens.egg-info -ErrorAction SilentlyContinue
```

### Step 2: Build the Packages

With your virtual environment activated, run the `build` command from the project root.

```bash
python -m build
```

This command will:
1.  Read the `[build-system]` section of `pyproject.toml` to determine the build backend (`setuptools`).
2.  Create a `build/` directory for intermediate files.
3.  Generate the final distributable packages and place them in a `dist/` directory.

## 3. Understanding the Output (`dist/` Directory)

After a successful build, the `dist/` directory will contain two types of files:

*   **Wheel (`.whl`)**:
    *   **Filename:** `sourcelens-0.2.0-py3-none-any.whl`
    *   **Description:** This is a **pre-built package**. It's the preferred format for distribution because `pip` can install it very quickly without needing to run a build process on the end-user's machine. The `-py3-none-any` suffix indicates it's a "universal" wheel compatible with any Python 3 on any platform (as it's pure Python).

*   **Source Distribution (`.tar.gz`)**:
    *   **Filename:** `sourcelens-0.2.0.tar.gz`
    *   **Description:** This is an archive of the raw source code, `pyproject.toml`, and other essential files. It serves as a fallback. When a user installs from a source distribution (sdist), `pip` must execute the build process on their machine, which can be slower and requires them to have the necessary build tools installed.

## 4. Local Testing Protocol (Critical)

**Never distribute a package without testing it locally first.** This must be done in a **completely separate and clean virtual environment** to simulate a real user's installation.

1.  **Create a Clean Test Environment:**
    ```bash
    # Deactivate your current development venv if you are in one
    # deactivate

    # Create a new, temporary environment
    python -m venv /tmp/sourcelens-test-env 

    # Activate it
    # On Linux/macOS:
    source /tmp/sourcelens-test-env/bin/activate
    # On Windows:
    # \tmp\sourcelens-test-env\Scripts\activate
    ```

2.  **Install from the Wheel File:**
    Use `pip` to install the `.whl` file you just created.
    ```bash
    # Make sure you are in the project's root directory
    pip install dist/sourcelens-0.2.0-py3-none-any.whl
    # (Use the exact filename from your dist/ folder)
    ```

3.  **Verify the Installation:**
    Check that the command-line script was installed correctly.
    ```bash
    # The command should be available in the new environment's PATH
    sourcelens --help
    ```
    If this works, try a basic run to ensure all runtime dependencies were correctly specified and installed. You may need to provide a `config.json` and API keys via environment variables for a full test.

4.  **Clean Up:**
    ```bash
    # Deactivate the test environment
    deactivate

    # Optionally, remove the temporary environment directory
    # rm -rf /tmp/sourcelens-test-env
    ```

## 5. Distribution to PyPI (Optional)

Once your package is built and tested, you can distribute it on the Python Package Index (PyPI).

*   **Tool:** The standard tool for uploading is `twine`. Install it: `pip install twine`.
*   **Command:** To upload everything in your `dist/` directory:
    ```bash
    twine upload dist/*
    ```
*   **Prerequisites:** This requires an account on [PyPI](https://pypi.org/) and an API token. For detailed instructions, refer to the official [Python Packaging User Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/).

