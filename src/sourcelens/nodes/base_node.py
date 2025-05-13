# src/sourcelens/nodes/base_node.py

"""Abstract base classes for processing nodes in the SourceLens workflow.

Defines the common structure and helper methods for standard and batch nodes,
integrating with the SourceLens internal flow engine.
"""

import logging
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Optional, TypeAlias, TypeVar

# Import Node and BatchNode from the integrated core flow engine
from sourcelens.core import BatchNode, Node

# Type alias for shared state dictionary
SharedState: TypeAlias = dict[str, Any]

# --- Type Variables ---
PrepResultType = TypeVar("PrepResultType")
ExecResultType = TypeVar("ExecResultType")
PrepItemType = TypeVar("PrepItemType")
ExecItemResultType = TypeVar("ExecItemResultType")
SharedValueType = TypeVar("SharedValueType")


class BaseNode(Node, ABC):  # Inherit directly from the imported Node
    """Abstract Base Class for standard processing nodes in the SourceLens flow."""

    _logger: logging.Logger  # Instance logger
    _supports_stacklevel: bool = sys.version_info >= (3, 8)

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseNode with retry parameters and logger.

        Args:
            max_retries: Maximum number of retries for the node execution
                         managed by the flow runner. Defaults to 0.
            wait: Wait time in seconds between retries. Defaults to 0.

        """
        super().__init__(max_retries=max_retries, wait=wait)  # Call Node's __init__
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def prep(self, shared: SharedState) -> PrepResultType:
        """Prepare input data for the execution phase.

        This method should be implemented by subclasses to gather and prepare
        all necessary data from the `shared` state that the `exec` method
        will require.

        Args:
            shared: The shared state dictionary containing data from previous
                    nodes or initial setup.

        Returns:
            Data prepared for the `exec` method. The specific type of this
            data (`PrepResultType`) is defined by the subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
            ValueError: If required data is missing from the shared state or
                        is invalid (implementation specific).

        """
        raise NotImplementedError

    @abstractmethod
    def exec(self, prep_res: PrepResultType) -> ExecResultType:
        """Execute the core logic of the node.

        This method should be implemented by subclasses to perform the primary
        task of the node, using the data provided by the `prep` phase.

        Args:
            prep_res: The result returned by the `prep` method. Its type
                      (`PrepResultType`) is defined by the subclass.

        Returns:
            The result of the node's execution. The specific type of this
            result (`ExecResultType`) is defined by the subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
            Exception: Can raise any exception if an error occurs during execution;
                       the flow engine's retry logic will handle it.

        """
        raise NotImplementedError

    @abstractmethod
    def post(self, shared: SharedState, prep_res: PrepResultType, exec_res: ExecResultType) -> None:
        """Update the shared state with the execution results.

        This method should be implemented by subclasses to take the results
        from the `exec` phase and update the `shared` state dictionary,
        making results available to subsequent nodes. In the SourceLens
        implementation, this method typically does not return an action string
        for flow control, as this is handled by the predefined flow structure.

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

    def _get_required_shared(self, shared: SharedState, key: str) -> SharedValueType:
        """Safely retrieve a required value from the shared state dictionary.

        Args:
            shared: The shared state dictionary to query.
            key: The key of the value to retrieve.

        Returns:
            The value associated with the key.

        Raises:
            ValueError: If the key is not found in the shared state or its
                        value is None.

        """
        value: Optional[SharedValueType] = shared.get(key)
        if value is None:
            error_msg = (
                f"Missing required key '{key}' or value is None in shared state for node {self.__class__.__name__}"
            )
            self._log_error(error_msg)  # Log before raising
            raise ValueError(error_msg)
        return value

    def _log_info(self, message: str, *args: object) -> None:
        """Log an informational message using the node's logger.

        Args:
            message: The message string to log.
            *args: Arguments to be merged into message.

        """
        if self._supports_stacklevel:
            self._logger.info(message, *args, stacklevel=2)
        else:  # pragma: no cover
            self._logger.info(message, *args)

    def _log_warning(self, message: str, *args: object) -> None:
        """Log a warning message using the node's logger.

        Args:
            message: The message string to log.
            *args: Arguments to be merged into message.

        """
        if self._supports_stacklevel:
            self._logger.warning(message, *args, stacklevel=2)
        else:  # pragma: no cover
            self._logger.warning(message, *args)

    def _log_error(self, message: str, *args: object, exc_info: bool = False) -> None:
        """Log an error message, optionally including exception info.

        Args:
            message: The message string to log.
            *args: Arguments to be merged into message.
            exc_info: If True, exception information is added to the
                      logging message. Defaults to False.

        """
        if self._supports_stacklevel:
            self._logger.error(message, *args, exc_info=exc_info, stacklevel=2)
        else:  # pragma: no cover
            self._logger.error(message, *args, exc_info=exc_info)


class BaseBatchNode(BatchNode, BaseNode, ABC):  # Inherit from imported BatchNode and our BaseNode
    """Abstract Base Class for batch processing nodes in the SourceLens flow."""

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseBatchNode.

        Args:
            max_retries: Maximum number of retries for each item's execution.
            wait: Wait time in seconds between retries.

        """
        super().__init__(max_retries=max_retries, wait=wait)
        # Ensure _logger is initialized from our BaseNode's hierarchy if not already
        if not hasattr(self, "_logger") or self._logger is None:  # Should be set by BaseNode's __init__ via Node
            self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def prep(self, shared: SharedState) -> Iterable[PrepItemType]:
        """Prepare an iterable of items for batch processing.

        Each item in the iterable will be passed to the `exec` method.

        Args:
            shared: The shared state dictionary.

        Returns:
            An iterable of items, where each item is of type `PrepItemType`
            defined by the subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError

    @abstractmethod
    def exec(self, item: PrepItemType) -> ExecItemResultType:  # This exec is for a single item
        """Execute the core logic for a single item in the batch.

        Args:
            item: A single item from the iterable returned by `prep`.
                  Its type (`PrepItemType`) is defined by the subclass.

        Returns:
            The result of processing the single item. Its type
            (`ExecItemResultType`) is defined by the subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError

    @abstractmethod
    def post(
        self,
        shared: SharedState,
        prep_res: Iterable[PrepItemType],  # This is the iterable of all items from prep
        exec_res_list: list[ExecItemResultType],  # This is the list of results from exec for each item
    ) -> None:
        """Update the shared state with the results from all batch items.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The iterable of items returned by the `prep` method.
            exec_res_list: A list containing the execution result for each item
                           processed by the `exec` method, passed by the flow runner.

        Returns:
            None.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError


# End of src/sourcelens/nodes/base_node.py
