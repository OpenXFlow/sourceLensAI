# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


"""Abstract base classes for processing nodes in the SourceLens workflow.

Defines the common structure and helper methods for standard and batch nodes,
integrating with the SourceLens internal flow engine. This version uses
descriptive method names (pre_execution, execution, post_execution) and
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
# These core classes now use pre_execution, execution, post_execution
from sourcelens.core import BatchNode as CoreBatchNode
from sourcelens.core import Node as CoreNode

# --- Type Variables for SourceLens specific node implementations ---
SLSharedContext: TypeAlias = dict[str, Any]  # Renamed from SLSharedState
"""Standard shared context type for all SourceLens nodes."""

SLPreparedInputs = TypeVar("SLPreparedInputs")  # Renamed from SLPrepResType
"""TypeVar for the result of a BaseNode's pre_execution method."""
SLExecutionResult = TypeVar("SLExecutionResult")  # Renamed from SLExecResType
"""TypeVar for the result of a BaseNode's execution method."""

SLBatchItem = TypeVar("SLBatchItem")  # Renamed from SLItemType
"""TypeVar for individual items in a batch processed by BaseBatchNode."""
SLBatchItemExecutionResult = TypeVar("SLBatchItemExecutionResult")  # Renamed
"""TypeVar for the result of execution on a single batch item in BaseBatchNode."""


class BaseNode(
    CoreNode[SLSharedContext, SLPreparedInputs, SLExecutionResult], ABC, Generic[SLPreparedInputs, SLExecutionResult]
):
    """Abstract Base Class for standard processing nodes in SourceLens.

    Inherits core lifecycle logic (pre_execution, execution, post_execution)
    and retry mechanisms from `sourcelens.core.Node`.
    This class is made generic over `SLPreparedInputs` and `SLExecutionResult`
    to be specified by concrete node implementations. The `SLSharedContext`
    is fixed as `dict[str, Any]`.
    """

    _logger: logging.Logger
    _supports_stacklevel: bool = sys.version_info >= (3, 8)

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseNode with retry parameters and a logger.

        The logger is specific to the concrete node's class name.
        Retry parameters are passed to the underlying core Node.

        Args:
            max_retries: Maximum number of retries for the node's `execution` phase.
                         If 0, the underlying Node's default (usually 1 attempt)
                         will be used.
            wait: Wait time in seconds between retries. Defaults to 0.
        """
        super().__init__(max_retries=max_retries if max_retries > 0 else 1, wait=wait)
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def pre_execution(self, shared_context: SLSharedContext) -> SLPreparedInputs:
        """Prepare input data for the main execution phase.

        Subclasses must implement this method to extract and transform data
        from the `shared_context` into a format suitable for the `execution` method.

        Args:
            shared_context: The shared context dictionary, providing data from
                            previous nodes or initial setup.

        Returns:
            The prepared data for the `execution` method, with a type corresponding
            to `SLPreparedInputs` specialized by the subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
            ValueError: Typically raised if required data is missing from `shared_context`
                        or if input data is invalid.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'pre_execution'")

    @abstractmethod
    def execution(self, prepared_inputs: SLPreparedInputs) -> SLExecutionResult:
        """Execute the core logic of the node.

        Subclasses must implement this method to perform the primary processing
        task of the node, using the `prepared_inputs` data.

        Args:
            prepared_inputs: The data prepared by the `pre_execution` method.

        Returns:
            The result of the node's execution, with a type corresponding
            to `SLExecutionResult` specialized by the subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
            Exception: Can raise any exception if an error occurs during execution.
                       The flow engine's retry logic will handle these based on
                       the `recoverable_errors` tuple in the `Node` class.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'execution'")

    @abstractmethod
    def post_execution(
        self, shared_context: SLSharedContext, prepared_inputs: SLPreparedInputs, execution_outputs: SLExecutionResult
    ) -> None:  # SourceLens nodes typically don't return an action string directly
        """Update the shared context with the execution results.

        Subclasses must implement this method to store the results from `execution_outputs`
        (and potentially `prepared_inputs` if needed for context) into the `shared_context`
        dictionary for consumption by subsequent nodes. SourceLens nodes typically do not
        return an action string; flow control is linear or managed by the Flow itself.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: The data prepared by the `pre_execution` method.
            execution_outputs: The result from the `execution` method.

        Returns:
            None. This method's primary side effect is modifying `shared_context`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'post_execution'")

    def _get_required_shared(self, shared_context: SLSharedContext, key: str) -> Any:
        """Safely retrieve a required value from the shared context dictionary.

        Args:
            shared_context: The shared context dictionary to query.
            key: The key of the value to retrieve.

        Returns:
            The value associated with the key. The caller is responsible for
            asserting or casting to the expected specific type.

        Raises:
            ValueError: If the key is not found in the shared context or its
                        value is None.
        """
        value: Optional[Any] = shared_context.get(key)
        if value is None:
            error_msg = (
                f"Missing required key '{key}' or value is None in shared context for node {self.__class__.__name__}"
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
    CoreBatchNode[SLSharedContext, SLBatchItem, SLBatchItemExecutionResult],
    ABC,
    Generic[SLBatchItem, SLBatchItemExecutionResult],
):
    """Abstract Base Class for batch processing nodes in SourceLens.

    Inherits batch execution logic from `sourcelens.core.BatchNode`.
    Concrete subclasses must implement `pre_execution` to return an iterable of
    `SLBatchItem`, `execution` to process the entire iterable of `SLBatchItem`
    (often by iterating and calling a helper for each item), and `post_execution`
    to handle the list of results.

    The retry logic from `CoreNode` (parent of `CoreBatchNode`) applies to the
    `execution` method of this `BaseBatchNode` as a whole (i.e., to the entire batch).
    If per-item retry is needed, it must be implemented within the subclass's
    `execution` method.

    This class is generic over `SLBatchItem` (the type of a single batch item) and
    `SLBatchItemExecutionResult` (the result of processing a single batch item).
    `SLSharedContext` is fixed as `dict[str, Any]`.
    """

    _logger: logging.Logger
    _supports_stacklevel: bool = sys.version_info >= (3, 8)

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the BaseBatchNode with retry and logging capabilities.

        Args:
            max_retries: Maximum number of retries for the entire batch's execution.
            wait: Wait time in seconds between retries for the entire batch.
        """
        super().__init__(max_retries=max_retries, wait=wait)
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def pre_execution(self, shared_context: SLSharedContext) -> Iterable[SLBatchItem]:  # type: ignore[override]
        """Prepare an iterable of `SLBatchItem` items for batch processing.

        This method is called once for the entire batch. The returned iterable's
        items will be passed as a whole to the `execution` method.

        Args:
            shared_context: The shared context dictionary, providing necessary data
                            to determine or generate the batch items.

        Returns:
            An iterable of items, where each item is of type `SLBatchItem`
            as specified by the concrete subclass.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'pre_execution'")

    @abstractmethod
    def execution(  # type: ignore[override]
        self, items_iterable: Iterable[SLBatchItem]
    ) -> list[SLBatchItemExecutionResult]:
        """Execute the core logic for all items in the batch.

        This method is called by the underlying `CoreBatchNode`'s execution
        logic (which inherits from `CoreNode` and includes retry for this entire method).
        Subclasses must implement this to iterate through `items_iterable` and
        process each item, returning a list of results. Per-item retry, if needed,
        should be handled within this method's loop.

        Args:
            items_iterable: An iterable of `SLBatchItem` from `pre_execution`.

        Returns:
            A list of results, one for each item, of type `SLBatchItemExecutionResult`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'execution' for the batch")

    @abstractmethod
    def post_execution(  # type: ignore[override]
        self,
        shared_context: SLSharedContext,
        prepared_items_iterable: Iterable[SLBatchItem],  # This is `prepared_inputs`
        execution_results_list: list[SLBatchItemExecutionResult],  # This is `execution_outputs`
    ) -> None:  # SourceLens batch nodes typically don't return an action string
        """Update the shared context with the results from all batch items.

        This method is called once after all items in the batch have been
        processed (or attempted) by the `execution` method.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_items_iterable: The iterable of items that was originally
                                     returned by `pre_execution`.
            execution_results_list: A list containing the execution result for each
                                    item, as returned by the `execution` method.

        Returns:
            None. This method's primary side effect is modifying `shared_context`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'post_execution'")

    def _get_required_shared(self, shared_context: SLSharedContext, key: str) -> Any:
        """Safely retrieve a required value from the shared context dictionary.

        Args:
            shared_context: The shared context dictionary to query.
            key: The key of the value to retrieve.

        Returns:
            The value associated with the key. Type is Any; caller should cast or type check.

        Raises:
            ValueError: If the key is not found or its value is None.
        """
        value: Optional[Any] = shared_context.get(key)
        if value is None:
            error_msg = (
                f"Missing required key '{key}' or value is None in shared context for node {self.__class__.__name__}"
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
