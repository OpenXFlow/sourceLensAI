# src/sourcelens/core/flow_engine_async.py

"""Asynchronous core of the PocketFlow-like workflow engine for SourceLens.

This module provides classes for defining asynchronous nodes (individual steps)
and flows (sequences of nodes) to orchestrate complex tasks. It supports
batch processing (sequential and parallel), retries, and conditional
transitions for asynchronous operations.

NOTE: This module contains classes for asynchronous workflow execution.
While the core SourceLens application currently operates synchronously,
these classes are retained for future enhancements and potential
asynchronous processing of I/O-bound tasks like LLM API calls.
"""

import asyncio
import copy
import warnings
from collections.abc import Iterable as TypingIterable
from typing import Any, Optional

# Import synchronous base classes from which async versions will inherit
from .flow_engine_sync import BaseNode, BatchFlow, BatchNode, Flow, Node


class AsyncNode(Node):  # Inherits from synchronous Node for retry logic structure
    """Asynchronous version of Node, using async/await for its main operations."""

    async def prep_async(self: "AsyncNode", shared: dict[str, Any]) -> Any:  # noqa: ANN401
        """Prepare asynchronous input data.

        To be implemented by subclasses for asynchronous preparation.

        Args:
            shared: The shared state dictionary.

        Returns:
            Data prepared for the `exec_async` method. Can be Any type.

        """
        # Default implementation calls synchronous prep if not overridden
        return super().prep(shared)

    async def exec_async(self: "AsyncNode", prep_res: Any) -> Any:  # noqa: ANN401
        """Execute asynchronous core logic.

        To be implemented by subclasses for asynchronous execution.

        Args:
            prep_res: The result returned by the `prep_async` method. Can be Any type.

        Returns:
            The result of the node's asynchronous execution. Can be Any type.

        """
        # This method MUST be overridden by subclasses wanting async exec
        error_msg = (
            f"{self.__class__.__name__} must implement exec_async or ensure exec "
            "is awaitable if inheriting from AsyncNode"
        )
        raise NotImplementedError(error_msg)

    async def exec_fallback_async(self: "AsyncNode", prep_res: Any, exc: Exception) -> Any:  # noqa: ANN401
        """Handle asynchronous fallback logic if all execution retries fail.

        The default behavior is to re-raise the last exception.
        Subclasses can override this to implement custom asynchronous fallback logic.

        Args:
            prep_res: The result from the `prep_async` method. Can be Any type.
            exc: The exception that occurred during the last execution attempt.

        Returns:
            A fallback result, or raises an exception. Can be Any type.

        Raises:
            Exception: Re-raises the input exception `exc` by default.

        """
        raise exc

    async def post_async(
        self: "AsyncNode",
        shared: dict[str, Any],
        prep_res: Any,  # noqa: ANN401
        exec_res: Any,  # noqa: ANN401
    ) -> Optional[str]:
        """Update shared state asynchronously after execution.

        To be implemented by subclasses for asynchronous post-processing.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The result returned by the `prep_async` method. Can be Any type.
            exec_res: The result returned by the `exec_async` method. Can be Any type.

        Returns:
            An optional action string.

        """
        # Default implementation calls synchronous post if not overridden
        # Corrected: Added noqa for prep_res
        return super().post(shared, prep_res, exec_res)  # prep_res: Any noqa: ANN401

    async def _exec_async_with_retry(self: "AsyncNode", prep_res: Any) -> Any:  # noqa: ANN401
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
                    warning_message = (
                        f"AsyncNode {self.__class__.__name__} failed on attempt "
                        f"{current_retry_attempt + 1}/{self.max_retries}. "
                        f"Retrying after {self.wait}s. Error: {e}"
                    )
                    warnings.warn(warning_message, stacklevel=2)
                    await asyncio.sleep(self.wait)
        fallback_exc = last_exception if last_exception else RuntimeError("Unknown async execution error after retries")
        return await self.exec_fallback_async(prep_res, fallback_exc)

    async def _run_async(self: "AsyncNode", shared: dict[str, Any]) -> Optional[str]:
        """Run internal asynchronous method: prep_async, _exec_async_with_retry, post_async."""
        prep_result: Any = await self.prep_async(shared)
        exec_result: Any = await self._exec_async_with_retry(prep_result)
        return await self.post_async(shared, prep_result, exec_result)

    async def run_async(self: "AsyncNode", shared: dict[str, Any]) -> Optional[str]:
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

    def _exec(self: "AsyncNode", prep_res: Any) -> Any:  # type: ignore[override] # noqa: ANN401
        error_msg = f"AsyncNode {self.__class__.__name__} must use asynchronous execution via _exec_async_with_retry."
        raise RuntimeError(error_msg)

    def _run(self: "AsyncNode", shared: dict[str, Any]) -> Optional[str]:  # type: ignore[override]
        """Prevent synchronous run for AsyncNode."""
        raise RuntimeError(f"AsyncNode {self.__class__.__name__} must be run with run_async().")


class AsyncBatchNode(AsyncNode, BatchNode):  # type: ignore[misc]
    """Asynchronous version of BatchNode. Processes items sequentially but asynchronously."""

    async def _exec_async_with_retry(  # type: ignore[override]
        self: "AsyncBatchNode", items: Optional[TypingIterable[Any]]
    ) -> list[Any]:
        """Asynchronously execute each item in the batch, calling parent's async exec.

        Args:
            items: An iterable of items returned by `prep_async`.

        Returns:
            A list of execution results, one for each item.

        """
        if items is None:
            return []
        return [await super(AsyncBatchNode, self)._exec_async_with_retry(item) for item in items]


class AsyncParallelBatchNode(AsyncNode, BatchNode):  # type: ignore[misc]
    """Asynchronous BatchNode that processes items in parallel using asyncio.gather."""

    async def _exec_async_with_retry(  # type: ignore[override]
        self: "AsyncParallelBatchNode", items: Optional[TypingIterable[Any]]
    ) -> list[Any]:
        """Asynchronously execute all items in the batch in parallel.

        Args:
            items: An iterable of items returned by `prep_async`.

        Returns:
            A list of execution results, one for each item, when all are complete.

        """
        if items is None:
            return []
        tasks = [super(AsyncParallelBatchNode, self)._exec_async_with_retry(item) for item in items]
        return await asyncio.gather(*tasks)


class AsyncFlow(Flow, AsyncNode):  # type: ignore[misc]
    """Asynchronous version of Flow, capable of running async and sync nodes."""

    async def _orch_async(
        self: "AsyncFlow", shared: dict[str, Any], params: Optional[dict[str, Any]] = None
    ) -> Optional[str]:
        """Orchestrate internal asynchronous logic for the flow.

        Args:
            shared: The shared state dictionary.
            params: Initial parameters for the flow.

        Returns:
            The action string returned by the last executed node in the flow.

        """
        if not self.start_node:
            warnings.warn("AsyncFlow has no start node defined. Nothing to execute.", stacklevel=2)
            return None

        current_node: Optional[BaseNode] = copy.copy(self.start_node)
        flow_params: dict[str, Any] = params if params is not None else {**self.params}
        last_action: Optional[str] = None

        while current_node:
            current_node.set_params(flow_params)
            if isinstance(current_node, AsyncNode):
                last_action = await current_node._run_async(shared)  # noqa: SLF001
            elif isinstance(current_node, BaseNode):
                last_action = current_node._run(shared)  # noqa: SLF001
            else:
                raise TypeError(f"Node {current_node.__class__.__name__} is not a recognized Node type for AsyncFlow.")
            current_node = copy.copy(self.get_next_node(current_node, last_action))
        return last_action

    async def _run_async(self: "AsyncFlow", shared: dict[str, Any]) -> Optional[str]:  # type: ignore[override]
        """Run internal asynchronous method for the flow."""
        prep_result: Any = await self.prep_async(shared)
        orch_result: Optional[str] = await self._orch_async(shared)
        return await self.post_async(shared, prep_result, orch_result)

    async def post_async(
        self: "AsyncFlow",
        shared: dict[str, Any],
        prep_res: Any,  # noqa: ANN401
        exec_res: Optional[str],  # noqa: ANN401
    ) -> Optional[str]:
        """Post-process asynchronously the entire flow.

        By default, returns the execution result of the orchestration (last action).
        Subclasses can override this.

        Args:
            shared: The shared state dictionary.
            prep_res: The result from the Flow's `prep_async` method. Can be Any.
            exec_res: The result from the Flow's orchestration (last action from last node).

        Returns:
            The `exec_res` by default.

        """
        return exec_res


class AsyncBatchFlow(AsyncFlow, BatchFlow):  # type: ignore[misc]
    """Asynchronous BatchFlow. Runs the async sub-flow for each item sequentially."""

    async def _run_async(self: "AsyncBatchFlow", shared: dict[str, Any]) -> None:  # type: ignore[override]
        """Asynchronously run the sub-flow for each item in the batch.

        Args:
            shared: The shared state dictionary.

        """
        batch_params_iterable: Optional[TypingIterable[dict[str, Any]]] = await self.prep_async(shared)
        if batch_params_iterable is None:
            batch_params_iterable = []

        results: list[Optional[str]] = []
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            result_for_item: Optional[str] = await self._orch_async(shared, current_run_params)
            results.append(result_for_item)
        await self.post_async(shared, batch_params_iterable, None)


class AsyncParallelBatchFlow(AsyncFlow, BatchFlow):  # type: ignore[misc]
    """Asynchronous BatchFlow that runs the async sub-flow for each item in parallel."""

    async def _run_async(self: "AsyncParallelBatchFlow", shared: dict[str, Any]) -> None:  # type: ignore[override]
        """Asynchronously run the sub-flow for each item in parallel using asyncio.gather.

        Args:
            shared: The shared state dictionary.

        """
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
