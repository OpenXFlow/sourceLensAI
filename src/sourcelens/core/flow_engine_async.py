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

"""Asynchronous core of the PocketFlow-like workflow engine for SourceLens.

This module provides classes for defining asynchronous nodes (individual steps)
and flows (sequences of nodes) to orchestrate complex tasks. It supports
batch processing (sequential and parallel), retries, and conditional
transitions for asynchronous operations. This version introduces generic types
for better type safety between P-E-P stages, mirroring the synchronous engine.

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

# Import synchronous base classes and type variables
from .flow_engine_sync import (
    BaseNode,
    BatchExecResType,
    BatchFlow,
    ExecResType,
    Flow,
    ItemType,
    Node,
    PrepResType,
    SharedStateType,
)


class AsyncNode(Node[SharedStateType, PrepResType, ExecResType]):
    """Asynchronous version of Node, using async/await for its main operations.

    This class is generic over `SharedStateType`, `PrepResType` (result of
    `prep_async`), and `ExecResType` (result of `exec_async`).
    """

    async def prep_async(self, shared: SharedStateType) -> PrepResType:
        """Prepare asynchronous input data.

        To be implemented by subclasses for asynchronous preparation.
        Defaults to calling the synchronous `prep` method if not overridden.

        Args:
            shared: The shared state dictionary, typed by `SharedStateType`.

        Returns:
            Data prepared for the `exec_async` method, of type `PrepResType`.

        """
        return super().prep(shared)

    @abstractmethod
    async def exec_async(self, prep_res: PrepResType) -> ExecResType:
        """Execute asynchronous core logic.

        This method MUST be implemented by concrete subclasses.

        Args:
            prep_res: The result returned by the `prep_async` method, of type `PrepResType`.

        Returns:
            The result of the node's asynchronous execution, of type `ExecResType`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement exec_async.")

    async def exec_fallback_async(self, prep_res: PrepResType, exc: Exception) -> ExecResType:
        """Handle asynchronous fallback logic if all execution retries fail.

        The default behavior is to re-raise the last exception.
        Subclasses can override this to implement custom asynchronous fallback logic.

        Args:
            prep_res: The result from the `prep_async` method, of type `PrepResType`.
            exc: The exception that occurred during the last execution attempt.

        Returns:
            A fallback result of type `ExecResType`, or raises an exception.

        Raises:
            Exception: Re-raises the input exception `exc` by default.

        """
        raise exc

    async def post_async(
        self,
        shared: SharedStateType,
        prep_res: PrepResType,
        exec_res: ExecResType,
    ) -> Optional[str]:
        """Update shared state asynchronously after execution.

        To be implemented by subclasses for asynchronous post-processing.
        Defaults to calling the synchronous `post` method if not overridden.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The result returned by the `prep_async` method.
            exec_res: The result returned by the `exec_async` method.

        Returns:
            An optional action string to determine the next node in a Flow.

        """
        return super().post(shared, prep_res, exec_res)

    async def _exec_async_with_retry(self, prep_res: PrepResType) -> ExecResType:
        """Wrap internal asynchronous execution with retry logic."""
        last_exception: Optional[Exception] = None
        for current_retry_attempt in range(self.max_retries):
            try:
                return await self.exec_async(prep_res)
            except Exception as e:  # noqa: BLE001
                last_exception = e
                if current_retry_attempt == self.max_retries - 1:
                    break
                if self.wait > 0:
                    # Shorter warning message construction
                    warning_message = (
                        f"AsyncNode {self.__class__.__name__} "
                        f"(prep: {type(prep_res).__name__}) "
                        f"failed attempt {current_retry_attempt + 1}/{self.max_retries}. "
                        f"Retrying after {self.wait}s. Error: {e}"
                    )
                    warnings.warn(warning_message, stacklevel=2)
                    await asyncio.sleep(self.wait)
        fallback_exc = last_exception if last_exception else RuntimeError("Unknown async execution error after retries")
        return await self.exec_fallback_async(prep_res, fallback_exc)

    async def _run_async(self, shared: SharedStateType) -> Optional[str]:
        """Run internal asynchronous method: prep_async, _exec_async_with_retry, post_async."""
        prep_result: PrepResType = await self.prep_async(shared)
        exec_result: ExecResType = await self._exec_async_with_retry(prep_result)
        return await self.post_async(shared, prep_result, exec_result)

    async def run_async(self, shared: SharedStateType) -> Optional[str]:
        """Run the asynchronous node's prep_async, exec_async, and post_async methods.

        Args:
            shared: The shared state dictionary.

        Returns:
            The action string returned by the `post_async` method.

        """
        if self.successors:
            warnings.warn(
                f"AsyncNode {self.__class__.__name__} has successors defined but is being run directly. "
                f"Successors will not be executed. Use an AsyncFlow.",
                stacklevel=2,
            )
        return await self._run_async(shared)

    def _exec(self, prep_res: PrepResType) -> ExecResType:  # type: ignore[override]
        error_msg = f"AsyncNode {self.__class__.__name__} must use asynchronous execution via _exec_async_with_retry."
        raise RuntimeError(error_msg)

    def _run(self, shared: SharedStateType) -> Optional[str]:  # type: ignore[override]
        raise RuntimeError(f"AsyncNode {self.__class__.__name__} must be run with run_async().")


async def _exec_one_item_async_with_retry_logic(
    node_instance: "AsyncBatchNode[Any, ItemType, BatchExecResType] | AsyncParallelBatchNode[Any, ItemType, BatchExecResType]",  # noqa: E501
    item: ItemType,
) -> BatchExecResType:
    """Execute a single item's async processing with retry logic.

    Args:
        node_instance: The instance of AsyncBatchNode or AsyncParallelBatchNode.
        item: The item to process.

    Returns:
        The result of processing the item.
    """
    last_exception: Optional[Exception] = None
    for attempt in range(node_instance.max_retries):
        try:
            return await node_instance.exec_async(item)
        except Exception as e:  # noqa: BLE001
            last_exception = e
            if attempt == node_instance.max_retries - 1:
                break
            if node_instance.wait > 0:
                # Shorter warning message construction
                warning_message = (
                    f"AsyncBatch item in {node_instance.__class__.__name__} "
                    f"(type: {type(item).__name__}) attempt {attempt + 1} failed. "
                    f"Retrying after {node_instance.wait}s. Error: {e}"
                )
                warnings.warn(warning_message, stacklevel=3)
                await asyncio.sleep(node_instance.wait)
    fallback_exc = last_exception if last_exception else RuntimeError("Unknown item processing error after retries")
    return await node_instance.exec_fallback_async(item, fallback_exc)  # type: ignore[arg-type]


class AsyncBatchNode(
    AsyncNode[SharedStateType, TypingIterable[ItemType], list[BatchExecResType]],
    Generic[SharedStateType, ItemType, BatchExecResType],
):
    """Asynchronous version of BatchNode. Processes items sequentially but asynchronously.

    Subclasses should implement:
    - `prep_async(self, shared: SharedStateType) -> TypingIterable[ItemType]`
    - `exec_async(self, item: ItemType) -> BatchExecResType` (for a single item)
    - `exec_fallback_async(self, item: ItemType, exc: Exception) -> BatchExecResType` (for single item fallback)
    - `post_async(self, shared: SharedStateType, prep_res:
       TypingIterable[ItemType], exec_res: list[BatchExecResType]) -> Optional[str]`
    """

    @abstractmethod
    async def exec_async(self, item: ItemType) -> BatchExecResType:  # type: ignore[override]
        """Execute asynchronous core logic for a single batch item.

        Args:
            item: The single item to process, of type `ItemType`.

        Returns:
            The result of processing the single item, of type `BatchExecResType`.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement exec_async to process a single item.")

    async def exec_fallback_async(self, item: ItemType, exc: Exception) -> BatchExecResType:  # type: ignore[override]
        """Handle fallback for a single failed batch item.

        Args:
            item: The item that failed processing.
            exc: The exception that occurred.

        Returns:
            A fallback result of type `BatchExecResType`.

        Raises:
            Exception: Re-raises `exc` by default.
        """
        raise exc

    async def _exec_async_with_retry(  # type: ignore[override]
        self, items_iterable: TypingIterable[ItemType]
    ) -> list[BatchExecResType]:
        """Asynchronously execute each item in the batch, applying retry logic individually.

        Args:
            items_iterable: An iterable of `ItemType` items from `prep_async`.

        Returns:
            A list of `BatchExecResType` results, one for each processed item.
        """
        results: list[BatchExecResType] = []
        for item in items_iterable:
            item_result = await _exec_one_item_async_with_retry_logic(self, item)
            results.append(item_result)
        return results


class AsyncParallelBatchNode(
    AsyncNode[SharedStateType, TypingIterable[ItemType], list[BatchExecResType]],
    Generic[SharedStateType, ItemType, BatchExecResType],
):
    """Asynchronous BatchNode that processes items in parallel using asyncio.gather.

    Subclasses should implement:
    - `prep_async(self, shared: SharedStateType) -> TypingIterable[ItemType]`
    - `exec_async(self, item: ItemType) -> BatchExecResType` (for a single item)
    - `exec_fallback_async(self, item: ItemType, exc: Exception) -> BatchExecResType` (for single item fallback)
    - `post_async(self, shared: SharedStateType, prep_res:
       TypingIterable[ItemType], exec_res: list[BatchExecResType]) -> Optional[str]`
    """

    @abstractmethod
    async def exec_async(self, item: ItemType) -> BatchExecResType:  # type: ignore[override]
        """Execute asynchronous core logic for a single batch item.

        Args:
            item: The single item to process, of type `ItemType`.

        Returns:
            The result of processing the single item, of type `BatchExecResType`.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement exec_async to process a single item.")

    async def exec_fallback_async(self, item: ItemType, exc: Exception) -> BatchExecResType:  # type: ignore[override]
        """Handle fallback for a single failed batch item in parallel context.

        Args:
            item: The item that failed processing.
            exc: The exception that occurred.

        Returns:
            A fallback result of type `BatchExecResType`.

        Raises:
            Exception: Re-raises `exc` by default.
        """
        raise exc

    async def _exec_async_with_retry(  # type: ignore[override]
        self, items_iterable: TypingIterable[ItemType]
    ) -> list[BatchExecResType]:
        """Asynchronously execute all items in the batch in parallel with retry for each.

        Args:
            items_iterable: An iterable of `ItemType` items from `prep_async`.

        Returns:
            A list of `BatchExecResType` results when all are complete.
        """
        tasks = [_exec_one_item_async_with_retry_logic(self, item) for item in items_iterable]
        gathered_results: list[BatchExecResType] = await asyncio.gather(*tasks)
        return gathered_results


class AsyncFlow(
    Flow[SharedStateType, PrepResType],
    AsyncNode[SharedStateType, PrepResType, Optional[str]],
    Generic[SharedStateType, PrepResType],
):  # type: ignore[misc]
    """Asynchronous version of Flow, capable of running async and sync nodes."""

    async def _orch_async(self, shared: SharedStateType, params: Optional[dict[str, Any]] = None) -> Optional[str]:
        """Orchestrate internal asynchronous logic for the flow."""
        if not self.start_node:
            warnings.warn("AsyncFlow has no start node defined. Nothing to execute.", stacklevel=2)
            return None

        current_node: Optional[BaseNode[Any, Any, Any]] = copy.copy(self.start_node)
        flow_params: dict[str, Any] = params if params is not None else {**self.params}
        last_action: Optional[str] = None

        while current_node:
            current_node.set_params(flow_params)
            if isinstance(current_node, AsyncNode):
                last_action = await current_node._run_async(shared)
            elif isinstance(current_node, Node):
                last_action = current_node._run(shared)
            else:
                error_msg = (
                    f"Node {current_node.__class__.__name__} is not a recognized Node or AsyncNode type for AsyncFlow."
                )
                raise TypeError(error_msg)
            next_node_candidate = self.get_next_node(current_node, last_action)
            current_node = copy.copy(next_node_candidate) if next_node_candidate else None
        return last_action

    async def _run_async(self, shared: SharedStateType) -> Optional[str]:
        """Run internal asynchronous method for the flow."""
        prep_result: PrepResType = await self.prep_async(shared)
        orch_result: Optional[str] = await self._orch_async(shared)
        return await self.post_async(shared, prep_result, orch_result)

    async def post_async(
        self,
        shared: SharedStateType,
        prep_res: PrepResType,
        exec_res: Optional[str],
    ) -> Optional[str]:
        """Post-process asynchronously the entire flow."""
        return exec_res


class AsyncBatchFlow(
    AsyncFlow[SharedStateType, TypingIterable[dict[str, Any]]],
    BatchFlow[SharedStateType],
    Generic[SharedStateType],
):  # type: ignore[misc]
    """Asynchronous BatchFlow. Runs the async sub-flow for each item sequentially."""

    async def _run_async(self, shared: SharedStateType) -> None:
        """Asynchronously run the sub-flow for each item in the batch."""
        batch_params_iterable: Optional[TypingIterable[dict[str, Any]]] = await self.prep_async(shared)
        if batch_params_iterable is None:
            batch_params_iterable = []

        results_agg: list[Optional[str]] = []
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            result_for_item: Optional[str] = await self._orch_async(shared, current_run_params)
            results_agg.append(result_for_item)
        await self.post_async(shared, batch_params_iterable, None)


class AsyncParallelBatchFlow(
    AsyncFlow[SharedStateType, TypingIterable[dict[str, Any]]],
    BatchFlow[SharedStateType],
    Generic[SharedStateType],
):  # type: ignore[misc]
    """Asynchronous BatchFlow that runs the async sub-flow for each item in parallel."""

    async def _run_async(self, shared: SharedStateType) -> None:
        """Asynchronously run the sub-flow for each item in parallel using asyncio.gather."""
        batch_params_iterable: Optional[TypingIterable[dict[str, Any]]] = await self.prep_async(shared)
        if batch_params_iterable is None:
            batch_params_iterable = []

        tasks: list[Any] = []
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            tasks.append(self._orch_async(shared, current_run_params))

        await asyncio.gather(*tasks)
        await self.post_async(shared, batch_params_iterable, None)


# End of src/sourcelens/core/flow_engine_async.py
