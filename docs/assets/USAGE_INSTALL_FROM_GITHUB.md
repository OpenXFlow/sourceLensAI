# Installing SourceLens from GitHub

If `sourceLens` is not yet available on the Python Package Index (PyPI), or if you wish to install a specific pre-release, a particular version, or the latest development code directly from its GitHub repository, you can use the methods described below. These approaches often rely on **GitHub Releases**, where developers may attach pre-built package files (like `.whl` or `.tar.gz`).

## 1. Installing from a Downloaded Wheel (`.whl`) File

This is often the recommended way to install a specific version if provided by the developers as a release asset.

*   **Navigate to GitHub Releases:** Go to the `sourceLens` GitHub repository (e.g., `https://github.com/openXFlow/sourceLensAI`) and find the "Releases" section on the right-hand sidebar.
*   **Select a Release:** Choose the release version you want to install (e.g., `v0.2.0`).
*   **Download the Asset:** Under the "Assets" dropdown for that release, look for a `.whl` (wheel) file. Download it to your local machine (e.g., `sourcelens-0.2.0-py3-none-any.whl`).
*   **Install using pip:** Open your terminal or command prompt, navigate to the directory where you saved the `.whl` file, and run:
    ```bash
    pip install sourcelens-0.2.0-py3-none-any.whl
    ```
    (Ensure you replace `sourcelens-0.2.0-py3-none-any.whl` with the exact name of the file you downloaded.)
*   `pip` will handle the installation process and any required dependencies specified in the package.

## 2. Installing Directly from a Wheel File URL on GitHub

If a direct URL to a `.whl` file asset on a GitHub Release is available, you can instruct `pip` to install from it directly:

```bash
pip install https://github.com/openXFlow/sourceLensAI/releases/download/v0.2.0/sourcelens-0.2.0-py3-none-any.whl
```
*(Note: The URL above is an illustrative example. You'll need to use the actual URL of the `.whl` file from the specific GitHub Release.)*

## 3. Installing Directly from the Git Repository

This method allows you to install the package from any branch, tag, or even a specific commit hash. It's particularly useful for accessing the latest development version or testing specific changes.

*   **To install the latest code from the `main` branch:**
    ```bash
    pip install git+https://github.com/openXFlow/sourceLensAI.git@main
    ```
*   **To install a specific tagged version (e.g., `v0.2.0`):**
    ```bash
    pip install git+https://github.com/openXFlow/sourceLensAI.git@v0.2.0
    ```
*   **To install from a specific commit hash:**
    ```bash
    pip install git+https://github.com/openXFlow/sourceLensAI.git@<full_commit_hash>
    ```
    Replace `<full_commit_hash>` with the actual commit SHA.

When using `pip install git+https...`, `pip` will clone the specified version of the repository into a temporary location and then attempt to build and install the package based on its `pyproject.toml` or `setup.py` file.

---

After successful installation using any of these methods, the `sourcelens` command should become available in your system's command line (provided your Python scripts directory is included in your system's PATH environment variable). This allows you to run `sourceLens` from any directory.
