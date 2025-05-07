# src/sourcelens/nodes/base_node.py

"""Abstract base classes for processing nodes in the SourceLens workflow.

Defines the common structure and helper methods for standard and batch nodes,
integrating with the PocketFlow library.
"""

import logging
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
# For specifying return types while maintaining some flexibility
PrepResultType = TypeVar("PrepResultType")
ExecResultType = TypeVar("ExecResultType")
PrepItemType = TypeVar("PrepItemType")
ExecItemResultType = TypeVar("ExecItemResultType")
# TypeVar for _get_required_shared
SharedValueType = TypeVar("SharedValueType")


class BaseNode(PocketFlowNode, ABC):
    """Abstract Base Class for standard processing nodes in the SourceLens flow."""

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseNode with retry parameters."""
        super().__init__(max_retries=max_retries, wait=wait)
        # Get logger instance specific to the subclass name
        self._logger = logging.getLogger(self.__class__.__name__)

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
        raise NotImplementedError

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
        raise NotImplementedError

    @abstractmethod
    def post(self, shared: SharedState, prep_res: PrepResultType, exec_res: ExecResultType) -> None:
        """Update the shared state with the execution results.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The result returned by the `prep` method.
            exec_res: The result returned by the `exec` method.

        Returns:
            None.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError

    # --- Helper Methods ---
    def _get_required_shared(self, shared: SharedState, key: str) -> SharedValueType:  # Using TypeVar
        """Safely retrieve a required value from the shared state dictionary.

        Args:
            shared: The shared state dictionary.
            key: The key to retrieve.

        Returns:
            The value associated with the key. The type is inferred by the caller
            or can be specified using type hints at the call site.

        Raises:
            ValueError: If the key is missing or its value is None.

        """
        value: Optional[SharedValueType] = shared.get(key)  # Assume type matches TypeVar
        if value is None:
            self._log_error("Missing required key '%s' in shared state.", key)
            raise ValueError(
                f"Missing required key '{key}' or value is None in shared state for node {self.__class__.__name__}"
            )
        return value

    def _log_info(self, message: str, *args: object) -> None:  # Changed Any to object
        """Log an informational message using the node's logger."""
        self._logger.info(message, *args)

    def _log_warning(self, message: str, *args: object) -> None:  # Changed Any to object
        """Log a warning message using the node's logger."""
        self._logger.warning(message, *args)

    def _log_error(
        self,
        message: str,
        *args: object,
        exc_info: bool = False,  # Changed Any to object
    ) -> None:
        """Log an error message, optionally including exception info.

        Args:
            message: The log message format string.
            *args: Arguments to format the message string.
            exc_info: If True, exception information is added to the log message.
                      Defaults to False.

        """
        self._logger.error(message, *args, exc_info=exc_info)


class BaseBatchNode(PocketFlowBatchNode, BaseNode, ABC):
    """Abstract Base Class for batch processing nodes in the SourceLens flow."""

    # Inherits __init__ from BaseNode

    @abstractmethod
    def prep(self, shared: SharedState) -> Iterable[PrepItemType]:
        """Prepare an iterable of items for batch processing.

        Args:
            shared: The shared state dictionary.

        Returns:
            An iterable where each element is prepared data for one execution item.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError

    @abstractmethod
    def exec(self, item: PrepItemType) -> ExecItemResultType:
        """Execute the core logic for a single item in the batch.

        Args:
            item: A single item prepared by the `prep` method.

        Returns:
            The result of processing the single item.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError

    @abstractmethod
    def post(
        self, shared: SharedState, prep_res: Iterable[PrepItemType], exec_res_list: list[ExecItemResultType]
    ) -> None:
        """Update the shared state with the results from all batch items.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The iterable returned by the `prep` method.
            exec_res_list: A list containing the results from executing `exec`
                           on each item yielded by `prep_res`.

        Returns:
            None.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError


# End of src/sourcelens/nodes/base_node.py
