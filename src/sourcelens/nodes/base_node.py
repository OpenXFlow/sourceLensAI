"""Abstract base classes for processing nodes in the SourceLens workflow.

Defines the common structure and helper methods for standard and batch nodes,
integrating with the PocketFlow library.
"""

import logging  # Moved import to top level
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Optional, TypeAlias, TypeVar

# Adjust imports based on your chosen flow library
try:
    from pocketflow import BatchNode as PocketFlowBatchNode
    from pocketflow import Node as PocketFlowNode
except ImportError:
    print("Warning: PocketFlow library not found. Using dummy classes for type checking.")
    # Define dummy classes
    class PocketFlowNode:
        """Dummy Node class if PocketFlow is not installed."""

        # D107: Added docstring
        def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
            """Initialize dummy node."""
            pass # pragma: no cover
    class PocketFlowBatchNode(PocketFlowNode):
        """Dummy BatchNode class if PocketFlow is not installed."""

        pass # pragma: no cover


# Type alias for shared state dictionary
SharedState: TypeAlias = dict[str, Any]

# --- Type Variables for more specific abstract method hints ---
PrepResultType = TypeVar("PrepResultType")
ExecResultType = TypeVar("ExecResultType")
PrepItemType = TypeVar("PrepItemType")
ExecItemResultType = TypeVar("ExecItemResultType")


class BaseNode(PocketFlowNode, ABC):
    """Abstract Base Class for standard processing nodes in the SourceLens flow."""

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseNode with retry parameters."""
        super().__init__(max_retries=max_retries, wait=wait)

    @abstractmethod
    def prep(self, shared: SharedState) -> PrepResultType:
        """Prepare input data for the execution phase."""
        pass

    @abstractmethod
    def exec(self, prep_res: PrepResultType) -> ExecResultType:
        """Execute the core logic of the node."""
        pass

    @abstractmethod
    def post(self, shared: SharedState, prep_res: PrepResultType, exec_res: ExecResultType) -> None:
        """Update the shared state with the execution results."""
        pass

    # --- Helper Methods ---
    def _get_required_shared(self, shared: SharedState, key: str) -> Any:
        """Safely retrieve a required value from the shared state dictionary."""
        value = shared.get(key)
        if value is None:
            raise ValueError(
                f"Missing required key '{key}' or value is None in shared state for node {self.__class__.__name__}"
            )
        return value

    def _log_info(self, message: str, *args: Any) -> None:
        """Log an informational message using the node's class name."""
        # Use module-level logger instance
        logging.getLogger(self.__class__.__name__).info(message, *args)

    def _log_warning(self, message: str, *args: Any) -> None:
        """Log a warning message using the node's class name."""
        logging.getLogger(self.__class__.__name__).warning(message, *args)

    def _log_error(
        self, message: str, *args: Any, exc: Optional[Exception] = None
    ) -> None:
        """Log an error message, optionally including exception info."""
        logger_instance = logging.getLogger(self.__class__.__name__)
        # Pass args for formatting, set exc_info based on `exc` presence
        logger_instance.error(message, *args, exc_info=exc is not None)


class BaseBatchNode(PocketFlowBatchNode, BaseNode, ABC):
     """Abstract Base Class for batch processing nodes in the SourceLens flow."""

     # Inherits __init__ from BaseNode

     @abstractmethod
     def prep(self, shared: SharedState) -> Iterable[PrepItemType]:
         """Prepare an iterable of items for batch processing."""
         pass

     @abstractmethod
     def exec(self, item: PrepItemType) -> ExecItemResultType:
         """Execute the core logic for a single item in the batch."""
         pass

     @abstractmethod
     def post(self, shared: SharedState, prep_res: Iterable[PrepItemType], exec_res_list: list[ExecItemResultType]) -> None:
         """Update the shared state with the results from all batch items."""
         # E501 fix: Wrapped long line in docstring
         pass

# End of src/sourcelens/nodes/base_node.py
