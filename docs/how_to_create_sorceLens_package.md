```markdown
# How to Create a Distributable Package for sourceLens

This guide explains how to build distributable packages (specifically wheels and source distributions) for the `sourceLens` project. These packages allow others to easily install `sourceLens` using `pip` without needing to clone the repository directly.

## 1. Prerequisites

*   **Working Project:** You should have the `sourceLens` project code locally, preferably cloned from the repository.
*   **Virtual Environment:** It's highly recommended to perform the build process within the project's activated virtual environment to ensure consistency.
*   **Build Tool:** Ensure you have the standard Python `build` package installed in your environment:
    ```bash
    pip install build
    ```
    *(Note: The `build` tool will use `setuptools` and `wheel` as specified in `pyproject.toml`'s `[build-system]` section, but `build` is the frontend command you typically use).*
*   **Complete `pyproject.toml`:** Verify that your `pyproject.toml` file contains accurate project metadata (name, version, description, dependencies, etc.) as described in `how_to_pyproject_toml.md`. The `version` number is particularly important as it will be part of the package filenames.

## 2. Cleaning Previous Builds (Optional but Recommended)

Before creating new packages, it's good practice to remove any artifacts from previous builds to ensure a clean state:

```bash
# Make sure you are in the project root directory (sourceLensAI/)
rm -rf build/ dist/ src/sourcelens.egg-info/
```
*(Use `rd /s /q build dist src\sourcelens.egg-info` on Windows Command Prompt or `Remove-Item -Recurse -Force build, dist, src/sourcelens.egg-info` in PowerShell)*

## 3. Building the Packages

The standard command to build both a wheel and a source distribution (sdist) using the configuration in `pyproject.toml` is:

```bash
# Ensure your virtual environment is activated
python -m build
```

*   This command reads `pyproject.toml` to understand how to build the project.
*   It invokes the build backend (setuptools) specified in `[build-system]`.
*   It performs the build process, potentially creating temporary files in a `build/` directory.
*   The final distributable packages are placed in a newly created `dist/` directory in your project root.

## 4. Understanding the Output Files (`dist/` directory)

After running `python -m build`, you will typically find two files inside the `dist/` directory:

*   **Wheel File (`.whl`)**:
    *   Example: `sourcelens-0.1.0-py3-none-any.whl` (Filename includes name, version, Python tag, ABI tag, platform tag).
    *   This is the **preferred** distribution format. It's essentially a pre-built package (like a zip file) containing the necessary code and metadata.
    *   `pip` can install wheels much faster than source distributions because it doesn't need to run a build step locally.
    *   The `-py3-none-any` part usually indicates it's a "universal" wheel compatible with any Python 3 installation on any OS (common for pure Python projects).
*   **Source Distribution (`.tar.gz`)**:
    *   Example: `sourcelens-0.1.0.tar.gz` (Filename includes name and version).
    *   This is an archive containing the raw source code (`src/` directory), `pyproject.toml`, `README.md`, `LICENSE`, and other necessary files defined by the build system.
    *   When a user installs from a source distribution (`sdist`), `pip` needs to execute the build process (defined in `pyproject.toml`) on their machine to create the final installed package. This requires the user to have the necessary build tools (like setuptools, wheel, potentially compilers if there were C extensions). It serves as a fallback if a suitable wheel isn't available.

## 5. Testing the Package Locally

Before distributing your package, it's crucial to test if it installs and runs correctly from the built files.

1.  **Create a *Separate* Test Environment:** Do *not* use your main development environment, as the package is already installed there in editable mode.
    ```bash
    # Deactivate current venv if active
    # deactivate (if needed)

    # Create a new temporary environment
    python -m venv /tmp/sourcelens_test_venv
    # Activate it (Linux/macOS example)
    source /tmp/sourcelens_test_venv/bin/activate
    # Or Windows: .\tmp\sourcelens_test_venv\Scripts\activate
    ```
2.  **Install from the Wheel File:** Install the package using the path to the `.whl` file you just created.
    ```bash
    # Navigate back to your project root (where dist/ is) if necessary
    cd /path/to/sourceLensAI

    # Install using the specific wheel file in dist/
    pip install dist/sourcelens-0.1.0-py3-none-any.whl
    # (Replace the filename with the actual one generated)
    ```
3.  **Run Basic Tests:** Verify the installation within the test environment.
    ```bash
    # Check if the command is available
    sourcelens --help

    # Try running it on the sample project (copy config.json to test env or use env vars)
    # You might need to copy your config.json to the current directory
    # or configure keys via environment variables for this test run.
    # cp config.json /tmp/config_for_test.json
    # export GEMINI_API_KEY=...
    # sourcelens --config /tmp/config_for_test.json --dir tests/sample_project
    ```
4.  **Deactivate and Clean Up:** Once testing is done, deactivate the test environment and optionally delete it.
    ```bash
    deactivate
    # rm -rf /tmp/sourcelens_test_venv (Optional)
    ```

## 6. Next Steps (Distribution - Optional)

Once you have successfully built and tested your packages locally, the next step is usually distribution, often via the Python Package Index (PyPI).

*   **Tool:** The standard tool for uploading packages is `twine`. Install it: `pip install twine`.
*   **Command:** Upload the contents of your `dist/` directory: `twine upload dist/*`.
*   **Prerequisites:** This requires creating an account on [PyPI](https://pypi.org/) and potentially configuring API tokens. Refer to the official Python packaging tutorials for detailed instructions on publishing.

## Conclusion

Building distributable packages using `python -m build` and `pyproject.toml` is the standard way to prepare your `sourceLens` project for sharing or installation. Creating wheels ensures faster and more reliable installations for end-users. Always test your built packages locally before distributing them.
```