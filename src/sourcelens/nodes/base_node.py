# src/sourcelens/nodes/base_node.py

"""Abstract base classes for processing nodes in the SourceLens workflow.

Defines the common structure and helper methods for standard and batch nodes,
integrating with the PocketFlow library.
"""

import logging
import sys
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
    class PocketFlowNode:  # type: ignore[no-redef]
        """Dummy Node class if PocketFlow is not installed."""

        def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
            """Initialize dummy node."""
            pass  # pragma: no cover

    class PocketFlowBatchNode(PocketFlowNode):  # type: ignore[no-redef]
        """Dummy BatchNode class if PocketFlow is not installed."""

        pass  # pragma: no cover


# Type alias for shared state dictionary
SharedState: TypeAlias = dict[str, Any]

# --- Type Variables ---
PrepResultType = TypeVar("PrepResultType")
ExecResultType = TypeVar("ExecResultType")
PrepItemType = TypeVar("PrepItemType")
ExecItemResultType = TypeVar("ExecItemResultType")
SharedValueType = TypeVar("SharedValueType")


class BaseNode(PocketFlowNode, ABC):
    """Abstract Base Class for standard processing nodes in the SourceLens flow."""

    _logger: logging.Logger
    _supports_stacklevel: bool = sys.version_info >= (3, 8)

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseNode with retry parameters and logger.

        Args:
            max_retries: Maximum number of retries for the node execution
                         managed by the flow runner. Defaults to 0.
            wait: Wait time in seconds between retries. Defaults to 0.

        """
        super().__init__(max_retries=max_retries, wait=wait)
        self._logger = logging.getLogger(self.__class__.__name__)
        # No internal exec result storage; relying on PocketFlow

    @abstractmethod
    def prep(self, shared: SharedState) -> PrepResultType:
        """Prepare input data for the execution phase.

        Args:
            shared: The shared state dictionary.

        Returns:
            Data prepared for the `exec` method. Type depends on the node.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
            ValueError: If required data is missing from the shared state.

        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def exec(self, prep_res: PrepResultType) -> ExecResultType:
        """Execute the core logic of the node.

        Args:
            prep_res: The result returned by the `prep` method.

        Returns:
            The result of the node's execution. Type depends on the node.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def post(self, shared: SharedState, prep_res: PrepResultType, exec_res: ExecResultType) -> None:
        """Update the shared state with the execution results.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The result returned by the `prep` method.
            exec_res: The result returned by the `exec` method, passed by the
                      flow runner (e.g., PocketFlow).

        Returns:
            None.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError  # pragma: no cover

    # --- _run override REMOVED ---
    # Rely on PocketFlow's internal _run or _orch mechanisms.

    # --- Helper Methods ---
    def _get_required_shared(self, shared: SharedState, key: str) -> SharedValueType:
        """Safely retrieve a required value from the shared state dictionary."""
        value: Optional[SharedValueType] = shared.get(key)
        if value is None:
            self._log_error("Missing required key '%s' in shared state.", key)
            raise ValueError(
                f"Missing required key '{key}' or value is None in shared state for node {self.__class__.__name__}"
            )
        return value

    def _log_info(self, message: str, *args: object) -> None:
        """Log an informational message using the node's logger."""
        if self._supports_stacklevel:
            self._logger.info(message, *args, stacklevel=2)
        else:
            self._logger.info(message, *args)

    def _log_warning(self, message: str, *args: object) -> None:
        """Log a warning message using the node's logger."""
        if self._supports_stacklevel:
            self._logger.warning(message, *args, stacklevel=2)
        else:
            self._logger.warning(message, *args)

    def _log_error(self, message: str, *args: object, exc_info: bool = False) -> None:
        """Log an error message, optionally including exception info."""
        if self._supports_stacklevel:
            self._logger.error(message, *args, exc_info=exc_info, stacklevel=2)
        else:
            self._logger.error(message, *args, exc_info=exc_info)


class BaseBatchNode(PocketFlowBatchNode, BaseNode, ABC):
    """Abstract Base Class for batch processing nodes in the SourceLens flow."""

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseBatchNode."""
        super().__init__(max_retries=max_retries, wait=wait)

    @abstractmethod
    def prep(self, shared: SharedState) -> Iterable[PrepItemType]:
        """Prepare an iterable of items for batch processing."""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def exec(self, item: PrepItemType) -> ExecItemResultType:  # Receives a single item
        """Execute the core logic for a single item in the batch."""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def post(
        self,
        shared: SharedState,
        prep_res: Iterable[PrepItemType],
        exec_res_list: list[ExecItemResultType],  # Receives list of results
    ) -> None:
        """Update the shared state with the results from all batch items."""
        raise NotImplementedError  # pragma: no cover


# End of src/sourcelens/nodes/base_node.py
