# src/sourcelens/nodes/base_node.py

"""Abstract base classes for processing nodes in the SourceLens workflow.

Defines the common structure and helper methods for standard and batch nodes,
integrating with the SourceLens internal flow engine.
"""

import logging
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterable  # Correct import
from typing import Any, Optional, TypeAlias, TypeVar

# Import Node and BatchNode from the integrated flow engine
from sourcelens.core.flow_engine import BatchNode as CoreBatchNode
from sourcelens.core.flow_engine import Node as CoreNode

# Type alias for shared state dictionary
SharedState: TypeAlias = dict[str, Any]

# --- Type Variables ---
PrepResultType = TypeVar("PrepResultType")
ExecResultType = TypeVar("ExecResultType")
PrepItemType = TypeVar("PrepItemType")
ExecItemResultType = TypeVar("ExecItemResultType")
SharedValueType = TypeVar("SharedValueType")


class BaseNode(CoreNode, ABC):  # Inherit from CoreNode
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

        The `exec_res` is directly passed by the flow engine. This method in
        SourceLens's BaseNode typically does not return an action string,
        as flow control decisions are simpler or handled by the structure.
        If a node needs to return an action, it should override `_run` or
        ensure its `post` method in `flow_engine.Node` returns it.
        For SourceLens, we assume `post` doesn't dictate flow control string.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The result returned by the `prep` method.
            exec_res: The result returned by the `exec` method, passed by the
                      flow runner (e.g., SourceLens flow engine).

        Returns:
            None.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError

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
            self._logger.info(message, *args)  # pragma: no cover

    def _log_warning(self, message: str, *args: object) -> None:
        """Log a warning message using the node's logger."""
        if self._supports_stacklevel:
            self._logger.warning(message, *args, stacklevel=2)
        else:
            self._logger.warning(message, *args)  # pragma: no cover

    def _log_error(self, message: str, *args: object, exc_info: bool = False) -> None:
        """Log an error message, optionally including exception info."""
        if self._supports_stacklevel:
            self._logger.error(message, *args, exc_info=exc_info, stacklevel=2)
        else:
            self._logger.error(message, *args, exc_info=exc_info)  # pragma: no cover


class BaseBatchNode(CoreBatchNode, BaseNode, ABC):
    """Abstract Base Class for batch processing nodes in the SourceLens flow."""

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseBatchNode."""
        super().__init__(max_retries=max_retries, wait=wait)
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def prep(self, shared: SharedState) -> Iterable[PrepItemType]:  # Use Iterable directly
        """Prepare an iterable of items for batch processing."""
        raise NotImplementedError

    @abstractmethod
    def exec(self, item: PrepItemType) -> ExecItemResultType:
        """Execute the core logic for a single item in the batch."""
        raise NotImplementedError

    @abstractmethod
    def post(
        self,
        shared: SharedState,
        prep_res: Iterable[PrepItemType],  # Use Iterable directly
        exec_res_list: list[ExecItemResultType],
    ) -> None:
        """Update the shared state with the results from all batch items.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The iterable of items returned by the `prep` method.
            exec_res_list: A list containing the execution result for each item
                           processed by the `exec` method, passed by the flow runner.

        """
        raise NotImplementedError


# End of src/sourcelens/nodes/base_node.py
