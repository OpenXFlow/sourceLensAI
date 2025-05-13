# src/sourcelens/nodes/base_node.py

"""Abstract base classes for processing nodes in the SourceLens workflow.

Defines the common structure and helper methods for standard and batch nodes,
integrating with the SourceLens internal flow engine. This version introduces
generic types for shared state, preparation results, and execution results,
enhancing type safety for node implementations.
"""

import logging
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Generic, Optional, TypeVar

from typing_extensions import TypeAlias

# Import Node and BatchNode from the integrated core flow engine
from sourcelens.core import BatchNode as CoreBatchNode
from sourcelens.core import Node as CoreNode

# --- Type Variables for SourceLens specific node implementations ---
SLSharedState: TypeAlias = dict[str, Any]
"""Standard shared state type for all SourceLens nodes."""

SLPrepResType = TypeVar("SLPrepResType")
"""TypeVar for the result of a BaseNode's prep method."""
SLExecResType = TypeVar("SLExecResType")
"""TypeVar for the result of a BaseNode's exec method."""

SLItemType = TypeVar("SLItemType")
"""TypeVar for individual items in a batch processed by BaseBatchNode."""
SLBatchItemExecResType = TypeVar("SLBatchItemExecResType")
"""TypeVar for the result of exec on a single batch item in BaseBatchNode."""


class BaseNode(CoreNode[SLSharedState, SLPrepResType, SLExecResType], ABC, Generic[SLPrepResType, SLExecResType]):
    """Abstract Base Class for standard processing nodes in SourceLens.

    Inherits core P-E-P logic and retry mechanisms from `sourcelens.core.Node`.
    This class is made generic over `SLPrepResType` and `SLExecResType`
    to be specified by concrete node implementations. The `SLSharedState`
    is fixed as `dict[str, Any]`.
    """

    _logger: logging.Logger
    _supports_stacklevel: bool = sys.version_info >= (3, 8)

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseNode with retry parameters and a logger.

        The logger is specific to the concrete node's class name.
        Retry parameters are passed to the underlying core Node.

        Args:
            max_retries: Maximum number of retries for the node's execution.
                         If 0, the underlying Node's default (usually 1 attempt)
                         will be used.
            wait: Wait time in seconds between retries. Defaults to 0.

        """
        super().__init__(max_retries=max_retries if max_retries > 0 else 1, wait=wait)
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def prep(self, shared: SLSharedState) -> SLPrepResType:
        """Prepare input data for the execution phase.

        Subclasses must implement this method to extract and transform data
        from the `shared` state into a format suitable for the `exec` method.

        Args:
            shared: The shared state dictionary, providing data from
                    previous nodes or initial setup.

        Returns:
            The prepared data for the `exec` method, with a type corresponding
            to `SLPrepResType` specialized by the subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
            ValueError: Typically raised if required data is missing from `shared`
                        or if input data is invalid.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'prep'")

    @abstractmethod
    def exec(self, prep_res: SLPrepResType) -> SLExecResType:
        """Execute the core logic of the node.

        Subclasses must implement this method to perform the primary processing
        task of the node, using the `prep_res` data.

        Args:
            prep_res: The data prepared by the `prep` method.

        Returns:
            The result of the node's execution, with a type corresponding
            to `SLExecResType` specialized by the subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
            Exception: Can raise any exception if an error occurs during execution.
                       The flow engine's retry logic will handle these.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'exec'")

    @abstractmethod
    def post(self, shared: SLSharedState, prep_res: SLPrepResType, exec_res: SLExecResType) -> None:
        """Update the shared state with the execution results.

        Subclasses must implement this method to store the results from `exec_res`
        (and potentially `prep_res` if needed for context) into the `shared`
        state dictionary for consumption by subsequent nodes.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The data prepared by the `prep` method.
            exec_res: The result from the `exec` method.

        Returns:
            None. This method's primary side effect is modifying `shared`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'post'")

    def _get_required_shared(self, shared: SLSharedState, key: str) -> Any:  # noqa: ANN401
        """Safely retrieve a required value from the shared state dictionary.

        Args:
            shared: The shared state dictionary to query.
            key: The key of the value to retrieve.

        Returns:
            The value associated with the key. The caller is responsible for
            asserting or casting to the expected specific type.

        Raises:
            ValueError: If the key is not found in the shared state or its
                        value is None.

        """
        value: Optional[Any] = shared.get(key)
        if value is None:
            error_msg = (
                f"Missing required key '{key}' or value is None in shared state for node {self.__class__.__name__}"
            )
            self._log_error(error_msg)
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
            exc_info: If True, exception information is added. Defaults to False.

        """
        if self._supports_stacklevel:
            self._logger.error(message, *args, exc_info=exc_info, stacklevel=2)
        else:  # pragma: no cover
            self._logger.error(message, *args, exc_info=exc_info)


class BaseBatchNode(
    CoreBatchNode[SLSharedState, SLItemType, SLBatchItemExecResType], ABC, Generic[SLItemType, SLBatchItemExecResType]
):
    """Abstract Base Class for batch processing nodes in SourceLens.

    Inherits batch execution logic from `sourcelens.core.BatchNode`.
    Concrete subclasses must implement `prep` to return an iterable of `SLItemType`,
    `exec` to process a single `SLItemType` and return `SLBatchItemExecResType`,
    and `post` to handle the list of results. Helper methods for logging and
    accessing shared state are included directly in this class.

    This class is generic over `SLItemType` (the type of a single batch item) and
    `SLBatchItemExecResType` (the result of `exec` on a single batch item).
    `SLSharedState` is fixed as `dict[str, Any]`.
    """

    _logger: logging.Logger
    _supports_stacklevel: bool = sys.version_info >= (3, 8)

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseBatchNode with retry and logging capabilities.

        Args:
            max_retries: Maximum number of retries for each item's execution
                         within the batch.
            wait: Wait time in seconds between retries for each item.

        """
        super().__init__(max_retries=max_retries, wait=wait)
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def prep(self, shared: SLSharedState) -> Iterable[SLItemType]:
        """Prepare an iterable of `SLItemType` items for batch processing.

        This method is called once for the entire batch. The returned iterable's
        items will be passed one by one to the `exec` method by the core
        batch processing logic.

        Args:
            shared: The shared state dictionary, providing necessary data
                    to determine or generate the batch items.

        Returns:
            An iterable of items, where each item is of type `SLItemType`
            as specified by the concrete subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'prep'")

    @abstractmethod
    def exec(self, item: SLItemType) -> SLBatchItemExecResType:
        """Execute the core logic for a single item in the batch.

        This method is called by the underlying `CoreBatchNode`'s execution
        logic for each `item` yielded by this node's `prep` method.
        The `type: ignore[override]` silences MyPy's Liskov Substitution
        Principle complaint, as this `exec` signature (for a single item)
        is intentionally specialized for batch processing, differing from the
        generic `exec(prep_res: PrepResType)` signature of `CoreNode`.

        Args:
            item: A single item from the iterable returned by `prep`.

        Returns:
            The result of processing the single item, of type `SLBatchItemExecResType`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'exec' for a single item")

    @abstractmethod
    def post(
        self, shared: SLSharedState, prep_res: Iterable[SLItemType], exec_res_list: list[SLBatchItemExecResType]
    ) -> None:
        """Update the shared state with the results from all batch items.

        This method is called once after all items in the batch have been
        processed (or attempted).

        Args:
            shared: The shared state dictionary to update.
            prep_res: The iterable of items that was originally returned by `prep`.
            exec_res_list: A list containing the execution result (of type
                           `SLBatchItemExecResType`) for each item processed by `exec`.

        Returns:
            None.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'post'")

    # Helper methods for logging and shared state access are part of BaseBatchNode
    def _get_required_shared(self, shared: SLSharedState, key: str) -> Any:  # noqa: ANN401
        """Safely retrieve a required value from the shared state dictionary.

        Args:
            shared: The shared state dictionary to query.
            key: The key of the value to retrieve.

        Returns:
            The value associated with the key. Type is Any; caller should cast or type check.

        Raises:
            ValueError: If the key is not found or its value is None.

        """
        value: Optional[Any] = shared.get(key)
        if value is None:
            error_msg = (
                f"Missing required key '{key}' or value is None in shared state for node {self.__class__.__name__}"
            )
            self._log_error(error_msg)
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
            exc_info: If True, exception information is added. Defaults to False.

        """
        if self._supports_stacklevel:
            self._logger.error(message, *args, exc_info=exc_info, stacklevel=2)
        else:  # pragma: no cover
            self._logger.error(message, *args, exc_info=exc_info)


# End of src/sourcelens/nodes/base_node.py
