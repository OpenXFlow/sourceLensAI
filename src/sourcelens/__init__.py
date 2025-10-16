# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""SourceLens Package.

An AI-powered tool to generate tutorials from codebases or web content
by analyzing source code or web pages and leveraging Large Language Models.
Its primary capabilities include generating code abstractions, documentation chapters,
diagrams, and identifying use case scenarios.
"""

# Define package version.
# This version should be kept in sync with the version in pyproject.toml.
__version__ = "0.3.0"  

# It's generally cleaner to let users import directly from submodules
# (e.g., from sourcelens.main import main) rather than re-exporting too much here,
# unless specific functions form the primary public API of the package.
#
# Example of a potential re-export if `main` function was intended as a direct API:
# from .main import main
#
# __all__ = [
# "main",
# "__version__",
# ]

# End of src/sourcelens/__init__.py
