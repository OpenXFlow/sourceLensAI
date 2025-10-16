# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Asynchronous core of the PocketFlow-like workflow engine for SourceLens.

This module provides classes for defining asynchronous nodes (individual steps)
and flows (sequences of nodes) to orchestrate complex tasks. It supports
batch processing (sequential and parallel), retries, and conditional
transitions for asynchronous operations. This version introduces generic types
for better type safety and uses more descriptive method names for node lifecycle.

NOTE: This module contains classes for asynchronous workflow execution.
While the core SourceLens application currently operates synchronously,
these classes are retained for future enhancements and potential
asynchronous processing of I/O-bound tasks like LLM API calls.
"""

import asyncio
import copy
import warnings
from abc import abstractmethod
from collections.abc import Iterable as TypingIterable
from typing import Any, Generic, Optional

from sourcelens.utils._exceptions import LlmApiError

# Import synchronous base classes and type variables, and new method names
from .flow_engine_sync import (
    BaseNode as SyncBaseNode,
)
from .flow_engine_sync import (
    BatchFlow as SyncBatchFlow,
)
from .flow_engine_sync import (
    BatchItemExecutionResultType,
    ExecutionResultType,
    FlowPreparedInputsType,
    ItemType,
    PreparedInputsType,
    SharedContextType,
)
from .flow_engine_sync import (
    Flow as SyncFlow,
)
from .flow_engine_sync import (
    Node as SyncNode,
)


class AsyncNode(SyncNode[SharedContextType, PreparedInputsType, ExecutionResultType]):
    """Asynchronous version of Node, using async/await for its main operations.

    This class is generic over `SharedContextType`, `PreparedInputsType` (result of
    `pre_execution_async`), and `ExecutionResultType` (result of `execution_async`).
    It inherits retry and fallback logic structure from the synchronous `Node`.
    """

    @abstractmethod
    async def pre_execution_async(self, shared_context: SharedContextType) -> PreparedInputsType:
        """Prepare asynchronous input data for the main execution phase.

        Subclasses MUST override this for asynchronous preparation logic.

        Args:
            shared_context: The shared context dictionary, typed by `SharedContextType`.

        Returns:
            Data prepared for the `execution_async` method, of type `PreparedInputsType`.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement pre_execution_async.")

    @abstractmethod
    async def execution_async(self, prepared_inputs: PreparedInputsType) -> ExecutionResultType:
        """Execute asynchronous core logic.

        This method MUST be implemented by concrete asynchronous subclasses.

        Args:
            prepared_inputs: The result returned by the `pre_execution_async` method,
                             of type `PreparedInputsType`.

        Returns:
            The result of the node's asynchronous execution, of type `ExecutionResultType`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement execution_async.")

    async def execution_fallback_async(
        self, prepared_inputs: PreparedInputsType, exc: Exception
    ) -> ExecutionResultType:
        """Handle asynchronous fallback logic if all execution retries fail.

        The default behavior is to re-raise the last exception.
        Subclasses can override this to implement custom asynchronous fallback logic.

        Args:
            prepared_inputs: The data from the `pre_execution_async` phase.
            exc: The exception that occurred during the last execution attempt.

        Returns:
            A fallback result of type `ExecutionResultType`, or raises an exception.

        Raises:
            Exception: Re-raises the input exception `exc` by default.
        """
        raise exc

    @abstractmethod
    async def post_execution_async(
        self,
        shared_context: SharedContextType,
        prepared_inputs: PreparedInputsType,
        execution_outputs: ExecutionResultType,
    ) -> Optional[str]:
        """Update shared context asynchronously after execution and determine next action.

        Subclasses MUST override this for asynchronous post-processing logic.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: The result returned by the `pre_execution_async` method.
            execution_outputs: The result returned by the `execution_async` method.

        Returns:
            An optional action string to determine the next node in an AsyncFlow.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement post_execution_async.")

    async def _execution_internal_async(self, prepared_inputs: PreparedInputsType) -> ExecutionResultType:
        """Wrap internal asynchronous execution with retry logic."""
        last_exception: Optional[Exception] = None
        recoverable_errors: tuple[type[Exception], ...] = (LlmApiError, asyncio.TimeoutError)

        for current_retry_attempt in range(self.max_retries):
            try:
                return await self.execution_async(prepared_inputs)
            except recoverable_errors as e:
                last_exception = e
                if current_retry_attempt == self.max_retries - 1:
                    break
                if self.wait > 0:
                    warn_msg_l1 = f"AsyncNode {self.__class__.__name__} (inputs: {type(prepared_inputs).__name__}) "
                    warn_msg_l2 = (
                        f"failed attempt {current_retry_attempt + 1}/{self.max_retries}. "
                        f"Retrying after {self.wait}s. Error: {e!s}"
                    )
                    warnings.warn(warn_msg_l1 + warn_msg_l2, stacklevel=2)
                    await asyncio.sleep(self.wait)

        fallback_exc = last_exception if last_exception else RuntimeError("Unknown async execution error after retries")
        return await self.execution_fallback_async(prepared_inputs, fallback_exc)

    async def _run_node_lifecycle_async(self, shared_context: SharedContextType) -> Optional[str]:
        """Run internal asynchronous lifecycle: pre_execution_async, _execution_internal_async, post_execution_async."""
        prepared_data: PreparedInputsType = await self.pre_execution_async(shared_context)
        execution_result: ExecutionResultType = await self._execution_internal_async(prepared_data)
        return await self.post_execution_async(shared_context, prepared_data, execution_result)

    async def run_standalone_async(self, shared_context: SharedContextType) -> Optional[str]:
        """Run the asynchronous node's full lifecycle standalone.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            The action string returned by `post_execution_async`.
        """
        if self.successors:
            warnings.warn(
                f"AsyncNode {self.__class__.__name__} has successors defined but is being run standalone_async. "
                f"Successors will not be executed. Use an AsyncFlow.",
                stacklevel=2,
            )
        return await self._run_node_lifecycle_async(shared_context)

    # Override synchronous methods to prevent accidental calls
    def pre_execution(self, shared_context: SharedContextType) -> PreparedInputsType:  # type: ignore[override]
        """Raise RuntimeError if synchronous pre_execution is called on an AsyncNode.

        AsyncNode instances should use `pre_execution_async`.

        Args:
            shared_context: The shared context.

        Raises:
            RuntimeError: Always.
        """
        error_msg = f"AsyncNode {self.__class__.__name__} must use pre_execution_async."
        raise RuntimeError(error_msg)

    def execution(self, prepared_inputs: PreparedInputsType) -> ExecutionResultType:  # type: ignore[override]
        """Raise RuntimeError if synchronous execution is called on an AsyncNode.

        AsyncNode instances should use `execution_async`.

        Args:
            prepared_inputs: The prepared inputs.

        Raises:
            RuntimeError: Always.
        """
        error_msg = f"AsyncNode {self.__class__.__name__} must use execution_async."
        raise RuntimeError(error_msg)

    def post_execution(  # type: ignore[override]
        self,
        shared_context: SharedContextType,
        prepared_inputs: PreparedInputsType,
        execution_outputs: ExecutionResultType,
    ) -> Optional[str]:
        """Raise RuntimeError if synchronous post_execution is called on an AsyncNode.

        AsyncNode instances should use `post_execution_async`.

        Args:
            shared_context: The shared context.
            prepared_inputs: The prepared inputs.
            execution_outputs: The execution outputs.

        Raises:
            RuntimeError: Always.
        """
        error_msg = f"AsyncNode {self.__class__.__name__} must use post_execution_async."
        raise RuntimeError(error_msg)

    def _execution_internal(self, prepared_inputs: PreparedInputsType) -> ExecutionResultType:  # type: ignore[override]
        """Raise RuntimeError if synchronous _execution_internal is called on an AsyncNode.

        Args:
            prepared_inputs: The prepared inputs.

        Raises:
            RuntimeError: Always.
        """
        error_msg = f"AsyncNode {self.__class__.__name__} must use _execution_internal_async."
        raise RuntimeError(error_msg)

    def _run_node_lifecycle(self, shared_context: SharedContextType) -> Optional[str]:  # type: ignore[override]
        """Raise RuntimeError if synchronous _run_node_lifecycle is called on an AsyncNode.

        Args:
            shared_context: The shared context.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError(f"AsyncNode {self.__class__.__name__} must be run with _run_node_lifecycle_async().")


async def _exec_one_item_async_with_retry(
    node_instance: "AsyncBatchNode[Any, ItemType, BatchItemExecutionResultType] | AsyncParallelBatchNode[Any, ItemType, BatchItemExecutionResultType]",  # noqa: E501
    item: ItemType,
) -> BatchItemExecutionResultType:
    """Execute a single item's async processing with retry logic.

    Helper function for AsyncBatchNode and AsyncParallelBatchNode.

    Args:
        node_instance: The instance of the batch node.
        item: The item to process.

    Returns:
        The result of processing the item.
    """
    last_exception: Optional[Exception] = None
    recoverable_item_errors: tuple[type[Exception], ...] = (LlmApiError, asyncio.TimeoutError)  # Example

    for attempt in range(node_instance.max_retries):
        try:
            return await node_instance.execution_async(item)  # type: ignore[arg-type]
        except recoverable_item_errors as e:  # Catch specific recoverable errors for items
            last_exception = e
            if attempt == node_instance.max_retries - 1:
                break
            if node_instance.wait > 0:
                warn_msg_l1 = (
                    f"AsyncBatch item in {node_instance.__class__.__name__} "
                    f"(type: {type(item).__name__}) attempt {attempt + 1} failed."
                )
                warn_msg_l2 = f" Retrying after {node_instance.wait}s. Error: {e!s}"
                warnings.warn(warn_msg_l1 + warn_msg_l2, stacklevel=3)
                await asyncio.sleep(node_instance.wait)
        # Non-specified errors will propagate immediately from execution_async

    fallback_exc = last_exception if last_exception else RuntimeError("Unknown item processing error after retries")
    return await node_instance.execution_fallback_async(item, fallback_exc)  # type: ignore[arg-type]


class AsyncBatchNode(
    AsyncNode[SharedContextType, TypingIterable[ItemType], list[BatchItemExecutionResultType]],
    Generic[SharedContextType, ItemType, BatchItemExecutionResultType],
):
    """Asynchronous BatchNode. Processes items sequentially using their async execution.

    Subclasses should implement:
    - `pre_execution_async(self, shared_context) -> TypingIterable[ItemType]`
    - `execution_async(self, item: ItemType) -> BatchItemExecutionResultType` (for a single item)
    - `execution_fallback_async(self, item: ItemType, exc: Exception) -> BatchItemExecutionResultType` (single item)
    - `post_execution_async(self, shared_context, prepared_inputs, execution_outputs)`
    """

    @abstractmethod
    async def execution_async(self, item: ItemType) -> BatchItemExecutionResultType:  # type: ignore[override]
        """Execute asynchronous core logic for a single batch item."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement execution_async to process a single item.")

    async def execution_fallback_async(  # type: ignore[override]
        self, item: ItemType, exc: Exception
    ) -> BatchItemExecutionResultType:
        """Handle fallback for a single failed batch item."""
        raise exc

    async def _execution_internal_async(  # type: ignore[override]
        self, items_iterable: TypingIterable[ItemType]
    ) -> list[BatchItemExecutionResultType]:
        """Asynchronously execute each item in the batch, applying retry logic individually."""
        results: list[BatchItemExecutionResultType] = []
        for item in items_iterable:
            item_result = await _exec_one_item_async_with_retry(self, item)
            results.append(item_result)
        return results


class AsyncParallelBatchNode(
    AsyncNode[SharedContextType, TypingIterable[ItemType], list[BatchItemExecutionResultType]],
    Generic[SharedContextType, ItemType, BatchItemExecutionResultType],
):
    """Asynchronous BatchNode that processes items in parallel using asyncio.gather.

    Retry logic is applied to each item's execution individually.
    Subclasses should implement methods as described in `AsyncBatchNode`.
    """

    @abstractmethod
    async def execution_async(self, item: ItemType) -> BatchItemExecutionResultType:  # type: ignore[override]
        """Execute asynchronous core logic for a single batch item (called in parallel)."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement execution_async to process a single item.")

    async def execution_fallback_async(  # type: ignore[override]
        self, item: ItemType, exc: Exception
    ) -> BatchItemExecutionResultType:
        """Handle fallback for a single failed batch item in parallel context."""
        raise exc

    async def _execution_internal_async(  # type: ignore[override]
        self, items_iterable: TypingIterable[ItemType]
    ) -> list[BatchItemExecutionResultType]:
        """Asynchronously execute all items in the batch in parallel with retry for each."""
        tasks = [_exec_one_item_async_with_retry(self, item) for item in items_iterable]
        gathered_results: list[BatchItemExecutionResultType] = await asyncio.gather(*tasks)
        return gathered_results


class AsyncFlow(
    SyncFlow[SharedContextType, FlowPreparedInputsType],
    AsyncNode[SharedContextType, FlowPreparedInputsType, Optional[str]],
    Generic[SharedContextType, FlowPreparedInputsType],
):  # type: ignore[misc]
    """Asynchronous version of Flow, capable of running async and sync nodes."""

    async def _orchestrate_async(
        self, shared_context: SharedContextType, flow_runtime_params: Optional[dict[str, Any]] = None
    ) -> Optional[str]:
        """Orchestrate internal asynchronous logic for the flow."""
        if not self.start_node:
            warnings.warn("AsyncFlow has no start node defined. Nothing to execute.", stacklevel=2)
            return None

        current_node: Optional[SyncBaseNode[Any, Any, Any]] = copy.copy(self.start_node)
        effective_params: dict[str, Any] = {**self.params, **(flow_runtime_params or {})}
        last_action: Optional[str] = None

        while current_node:
            current_node.set_params(effective_params)
            if isinstance(current_node, AsyncNode):
                last_action = await current_node._run_node_lifecycle_async(shared_context)
            elif isinstance(current_node, SyncBaseNode):
                last_action = current_node._run_node_lifecycle(shared_context)
            else:
                error_msg = f"Node {current_node.__class__.__name__} is not a recognized SyncBaseNode or AsyncNode."
                raise TypeError(error_msg)
            next_node_candidate = self.get_next_node(current_node, last_action)
            current_node = copy.copy(next_node_candidate) if next_node_candidate else None
        return last_action

    async def _run_node_lifecycle_async(self, shared_context: SharedContextType) -> Optional[str]:  # type: ignore[override]
        """Run internal asynchronous lifecycle for the flow."""
        prepared_flow_data: FlowPreparedInputsType = await self.pre_execution_async(shared_context)
        orchestration_result: Optional[str] = await self._orchestrate_async(shared_context, self.params)
        return await self.post_execution_async(shared_context, prepared_flow_data, orchestration_result)

    @abstractmethod
    async def pre_execution_async(self, shared_context: SharedContextType) -> FlowPreparedInputsType:  # type: ignore[override]
        """Prepare for the asynchronous flow execution.

        Subclasses should implement this to perform any async setup needed
        before the flow's child nodes are orchestrated.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            Prepared inputs for the flow's execution, if any.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement pre_execution_async.")

    @abstractmethod
    async def post_execution_async(  # type: ignore[override]
        self,
        shared_context: SharedContextType,
        prepared_inputs: FlowPreparedInputsType,
        execution_outputs: Optional[str],
    ) -> Optional[str]:
        """Post-process asynchronously the entire flow.

        Args:
            shared_context: The shared context dictionary.
            prepared_inputs: The data from `pre_execution_async`.
            execution_outputs: The result from the flow's orchestration.

        Returns:
            The `execution_outputs` by default, or custom logic.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement post_execution_async.")


class AsyncBatchFlow(
    AsyncFlow[SharedContextType, TypingIterable[dict[str, Any]]],
    SyncBatchFlow[SharedContextType],
    Generic[SharedContextType],
):  # type: ignore[misc]
    """Asynchronous BatchFlow. Runs the async sub-flow for each item sequentially."""

    @abstractmethod
    async def pre_execution_async(  # type: ignore[override]
        self, shared_context: SharedContextType
    ) -> TypingIterable[dict[str, Any]]:
        """Prepare an iterable of parameter dictionaries for batch processing.

        This method is called once before processing the batch. Each dictionary
        yielded or returned will be used as parameters for one asynchronous
        run of the sub-flow defined by this `AsyncBatchFlow`.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            An iterable of dictionaries, each for a sub-flow run.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement pre_execution_async to yield batch parameters."
        )

    async def _run_node_lifecycle_async(self, shared_context: SharedContextType) -> None:  # type: ignore[override]
        """Asynchronously run the sub-flow for each item in the batch."""
        batch_params_iterable: TypingIterable[dict[str, Any]] = await self.pre_execution_async(shared_context)
        results_agg: list[Optional[str]] = []
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            result_for_item: Optional[str] = await self._orchestrate_async(shared_context, current_run_params)
            results_agg.append(result_for_item)
        await self.post_execution_async(shared_context, batch_params_iterable, None)


class AsyncParallelBatchFlow(
    AsyncFlow[SharedContextType, TypingIterable[dict[str, Any]]],
    SyncBatchFlow[SharedContextType],
    Generic[SharedContextType],
):  # type: ignore[misc]
    """Asynchronous BatchFlow that runs the async sub-flow for each item in parallel."""

    @abstractmethod
    async def pre_execution_async(  # type: ignore[override]
        self, shared_context: SharedContextType
    ) -> TypingIterable[dict[str, Any]]:
        """Prepare an iterable of parameter dictionaries for parallel batch processing.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            An iterable of dictionaries, each for a sub-flow run in parallel.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement pre_execution_async to yield batch parameters."
        )

    async def _run_node_lifecycle_async(self, shared_context: SharedContextType) -> None:  # type: ignore[override]
        """Asynchronously run the sub-flow for each item in parallel using asyncio.gather."""
        batch_params_iterable: TypingIterable[dict[str, Any]] = await self.pre_execution_async(shared_context)
        tasks: list[Any] = []
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            tasks.append(self._orchestrate_async(shared_context, current_run_params))
        await asyncio.gather(*tasks)
        await self.post_execution_async(shared_context, batch_params_iterable, None)


# End of src/sourcelens/core/flow_engine_async.py
