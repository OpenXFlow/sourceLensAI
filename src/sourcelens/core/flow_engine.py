# src/sourcelens/core/flow_engine.py

"""PocketFlow: A simple, flexible library for creating and running workflows.

This module provides classes for defining nodes (individual steps) and flows
(sequences of nodes) to orchestrate complex tasks. It supports synchronous
and asynchronous operations, batch processing, retries, and conditional
transitions.

This code was originally from the 'pocketflow' library and has been
integrated into SourceLens for direct use and potential future customization.
"""

import asyncio
import copy
import time
import warnings
from collections.abc import Iterable as TypingIterable
from typing import Any, Optional


class BaseNode:
    """Base class for all nodes in a PocketFlow workflow."""

    def __init__(self: "BaseNode") -> None:
        """Initialize a BaseNode."""
        self.params: dict[str, Any] = {}
        self.successors: dict[str, BaseNode] = {}

    def set_params(self: "BaseNode", params: dict[str, Any]) -> None:
        """Set parameters for the node.

        Args:
            params: A dictionary of parameters.

        """
        self.params = params

    def next(self: "BaseNode", node: "BaseNode", action: str = "default") -> "BaseNode":
        """Define the next node in the flow for a given action.

        Args:
            node: The successor node.
            action: The action string that triggers transition to this node.
                    Defaults to "default".

        Returns:
            The successor node, allowing for chaining.

        """
        if action in self.successors:
            warnings.warn(
                f"Overwriting successor for action '{action}' in node {self.__class__.__name__}", stacklevel=2
            )
        self.successors[action] = node
        return node

    def prep(self: "BaseNode", shared: dict[str, Any]) -> Any:  # noqa: ANN401
        """Prepare input data for the execution phase.

        To be implemented by subclasses.

        Args:
            shared: The shared state dictionary.

        Returns:
            Data prepared for the `exec` method. Can be Any type.

        """
        return None

    def exec(self: "BaseNode", prep_res: Any) -> Any:  # noqa: ANN401
        """Execute the core logic of the node.

        To be implemented by subclasses.

        Args:
            prep_res: The result returned by the `prep` method. Can be Any type.

        Returns:
            The result of the node's execution. Can be Any type.

        """
        return None

    def post(
        self: "BaseNode",
        shared: dict[str, Any],
        prep_res: Any,  # noqa: ANN401
        exec_res: Any,  # noqa: ANN401, ANN401
    ) -> Optional[str]:
        """Update the shared state with the execution results.

        To be implemented by subclasses.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The result returned by the `prep` method. Can be Any type.
            exec_res: The result returned by the `exec` method. Can be Any type.

        Returns:
            An optional action string to determine the next node in a Flow.
            If None or "default" is returned, the "default" successor is chosen.

        """
        return None

    def _exec(self: "BaseNode", prep_res: Any) -> Any:  # noqa: ANN401, ANN401
        """Wrap internal execution."""
        return self.exec(prep_res)

    def _run(self: "BaseNode", shared: dict[str, Any]) -> Optional[str]:
        """Orchestrate internal run: prep, exec, and post.

        Args:
            shared: The shared state dictionary.

        Returns:
            The action string returned by the `post` method.

        """
        prep_result: Any = self.prep(shared)
        exec_result: Any = self._exec(prep_result)
        return self.post(shared, prep_result, exec_result)

    def run(self: "BaseNode", shared: dict[str, Any]) -> Optional[str]:
        """Run the node's prep, exec, and post methods.

        This is typically used for running a single node in isolation.
        For running a sequence of nodes, use a Flow.

        Args:
            shared: The shared state dictionary.

        Returns:
            The action string returned by the `post` method.

        """
        if self.successors:
            warnings.warn(
                f"Node {self.__class__.__name__} has successors defined but is being run directly. "
                f"Successors will not be executed. Use a Flow to run a sequence of nodes.",
                stacklevel=2,
            )
        return self._run(shared)

    def __rshift__(self: "BaseNode", other: "BaseNode") -> "BaseNode":
        """Syntactic sugar for `self.next(other, "default")`.

        Allows defining simple sequential flows like: node1 >> node2 >> node3.

        Args:
            other: The next node in the sequence.

        Returns:
            The `other` node, allowing for chaining.

        """
        return self.next(other)

    def __sub__(self: "BaseNode", action: str) -> "_ConditionalTransition":
        """Start a conditional transition definition.

        Allows syntax like: node1 - "success" >> node_on_success.

        Args:
            action: The action string for the conditional transition.

        Returns:
            A _ConditionalTransition helper object.

        Raises:
            TypeError: If action is not a string.

        """
        if isinstance(action, str):
            return _ConditionalTransition(self, action)
        raise TypeError(f"Action for conditional transition must be a string, got {type(action).__name__}")


class _ConditionalTransition:
    """Helper class for defining conditional transitions using the '-' operator."""

    def __init__(self: "_ConditionalTransition", src_node: BaseNode, action: str) -> None:
        """Initialize a _ConditionalTransition.

        Args:
            src_node: The source node of the transition.
            action: The action string.

        """
        self.source_node: BaseNode = src_node
        self.action: str = action

    def __rshift__(self: "_ConditionalTransition", target_node: BaseNode) -> BaseNode:
        """Complete the conditional transition by defining the target node.

        Args:
            target_node: The target node for this conditional transition.

        Returns:
            The target_node, allowing for further chaining if needed.

        """
        return self.source_node.next(target_node, self.action)


class Node(BaseNode):
    """A node with built-in retry logic for its execution phase."""

    def __init__(self: "Node", max_retries: int = 1, wait: int = 0) -> None:
        """Initialize a Node with retry parameters.

        Args:
            max_retries: Maximum number of execution attempts (default is 1, meaning no retries).
            wait: Time in seconds to wait between retries (default is 0).

        """
        super().__init__()
        self.max_retries: int = max(1, max_retries)
        self.wait: int = wait

    def exec_fallback(self: "Node", prep_res: Any, exc: Exception) -> Any:  # noqa: ANN401, ANN401
        """Handle fallback logic if all execution retries fail.

        The default behavior is to re-raise the last exception.
        Subclasses can override this to implement custom fallback logic.

        Args:
            prep_res: The result from the `prep` method. Can be Any type.
            exc: The exception that occurred during the last execution attempt.

        Returns:
            A fallback result, or raises an exception. Can be Any type.

        Raises:
            Exception: Re-raises the input exception `exc` by default.

        """
        raise exc

    def _exec(self: "Node", prep_res: Any) -> Any:  # noqa: ANN401, ANN401
        """Wrap internal execution with retry logic."""
        last_exception: Optional[Exception] = None
        for current_retry_attempt in range(self.max_retries):
            try:
                return self.exec(prep_res)
            except Exception as e:  # noqa: BLE001
                last_exception = e
                if current_retry_attempt == self.max_retries - 1:
                    break
                if self.wait > 0:
                    warning_message = (
                        f"Node {self.__class__.__name__} failed on attempt "
                        f"{current_retry_attempt + 1}/{self.max_retries}. "
                        f"Retrying after {self.wait}s. Error: {e}"
                    )
                    warnings.warn(warning_message, stacklevel=2)
                    time.sleep(self.wait)
        fallback_exc = last_exception if last_exception else RuntimeError("Unknown execution error after retries")
        return self.exec_fallback(prep_res, fallback_exc)


class BatchNode(Node):
    """A node that processes a batch of items.

    The `prep` method is expected to return an iterable of items.
    The `exec` method will be called for each item in the batch.
    """

    def _exec(self: "BatchNode", items: Optional[TypingIterable[Any]]) -> list[Any]:
        """Wrap internal execution for batch processing.

        Calls the `_exec` method of the parent `Node` class for each item.
        This ensures that retry logic from `Node` is applied per item.

        Args:
            items: An iterable of items returned by `prep`.

        Returns:
            A list of execution results, one for each item.

        """
        if items is None:
            return []
        return [super(BatchNode, self)._exec(item) for item in items]


class Flow(BaseNode):
    """Orchestrates the execution of a sequence of connected nodes."""

    def __init__(self: "Flow", start: Optional[BaseNode] = None) -> None:
        """Initialize a Flow.

        Args:
            start: The starting node of the flow. Can also be set later using `flow.start()`.

        """
        super().__init__()
        self.start_node: Optional[BaseNode] = start

    def start(self: "Flow", start_node: BaseNode) -> BaseNode:
        """Set the starting node of the flow.

        Args:
            start_node: The node to start the flow execution from.

        Returns:
            The `start_node`, allowing for chaining.

        """
        self.start_node = start_node
        return start_node

    def get_next_node(self: "Flow", current_node: BaseNode, action: Optional[str]) -> Optional[BaseNode]:
        """Determine the next node based on the current node and its returned action.

        Args:
            current_node: The node that just finished execution.
            action: The action string returned by `current_node.post()`.

        Returns:
            The next node to execute, or None if the flow ends.

        """
        resolved_action: str = action if isinstance(action, str) else "default"
        next_node: Optional[BaseNode] = current_node.successors.get(resolved_action)

        if not next_node and current_node.successors:
            warnings.warn(
                f"Flow ends: Action '{resolved_action}' returned by {current_node.__class__.__name__} "
                f"not found in its defined successors: {list(current_node.successors.keys())}",
                stacklevel=2,
            )
        elif not next_node and not current_node.successors:
            pass

        return next_node

    def _orch(self: "Flow", shared: dict[str, Any], params: Optional[dict[str, Any]] = None) -> Optional[str]:
        """Orchestrate internal logic for running the flow.

        Args:
            shared: The shared state dictionary.
            params: Initial parameters for the flow.

        Returns:
            The action string returned by the last executed node in the flow.

        """
        if not self.start_node:
            warnings.warn("Flow has no start node defined. Nothing to execute.", stacklevel=2)
            return None

        current_node: Optional[BaseNode] = copy.copy(self.start_node)
        flow_params: dict[str, Any] = params if params is not None else {**self.params}
        last_action: Optional[str] = None

        while current_node:
            current_node.set_params(flow_params)
            last_action = current_node._run(shared)  # noqa: SLF001
            current_node = copy.copy(self.get_next_node(current_node, last_action))

        return last_action

    def _run(self: "Flow", shared: dict[str, Any]) -> Optional[str]:
        """Run internal method for the flow."""
        prep_result: Any = self.prep(shared)
        orch_result: Optional[str] = self._orch(shared)
        return self.post(shared, prep_result, orch_result)

    def post(self: "Flow", shared: dict[str, Any], prep_res: Any, exec_res: Optional[str]) -> Optional[str]:  # noqa: ANN401
        """Post-process the entire flow.

        By default, returns the execution result of the orchestration (last action).
        Subclasses can override this.

        Args:
            shared: The shared state dictionary.
            prep_res: The result from the Flow's `prep` method. Can be Any.
            exec_res: The result from the Flow's orchestration (last action from last node).

        Returns:
            The `exec_res` by default.

        """
        return exec_res


class BatchFlow(Flow):
    """A flow that processes a batch of items.

    The `prep` method of this flow is expected to return an iterable.
    The entire sequence of nodes defined in the flow will be executed
    for each item in the batch.
    """

    def _run(self: "BatchFlow", shared: dict[str, Any]) -> None:
        """Run internal method for batch flow execution."""
        batch_params_iterable: Optional[TypingIterable[dict[str, Any]]] = self.prep(shared)
        if batch_params_iterable is None:
            batch_params_iterable = []

        results: list[Optional[str]] = []
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            result_for_item: Optional[str] = self._orch(shared, current_run_params)
            results.append(result_for_item)

        self.post(shared, batch_params_iterable, None)


# --- Asynchronous Counterparts ---


class AsyncNode(Node):
    """Asynchronous version of Node, using async/await."""

    async def prep_async(self: "AsyncNode", shared: dict[str, Any]) -> Any:  # noqa: ANN401
        """Prepare asynchronous input data."""
        return None

    async def exec_async(self: "AsyncNode", prep_res: Any) -> Any:  # noqa: ANN401
        """Execute asynchronous core logic."""
        return None

    async def exec_fallback_async(self: "AsyncNode", prep_res: Any, exc: Exception) -> Any:  # noqa: ANN401, ANN401
        """Handle asynchronous fallback logic."""
        raise exc

    async def post_async(
        self: "AsyncNode",
        shared: dict[str, Any],
        prep_res: Any,  # noqa: ANN401
        exec_res: Any,  # noqa: ANN401, ANN401
    ) -> Optional[str]:
        """Update shared state asynchronously."""
        return None

    async def _exec(self: "AsyncNode", prep_res: Any) -> Any:  # type: ignore[override] # noqa: ANN401, ANN401
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
        """Run internal asynchronous method."""
        prep_result: Any = await self.prep_async(shared)
        exec_result: Any = await self._exec(prep_result)  # type: ignore[assignment]
        return await self.post_async(shared, prep_result, exec_result)

    async def run_async(self: "AsyncNode", shared: dict[str, Any]) -> Optional[str]:
        """Run the asynchronous node's prep, exec, and post methods."""
        if self.successors:
            warnings.warn(
                f"AsyncNode {self.__class__.__name__} has successors defined but is being run directly. "
                f"Successors will not be executed. Use an AsyncFlow.",
                stacklevel=2,
            )
        return await self._run_async(shared)

    def _run(self: "AsyncNode", shared: dict[str, Any]) -> Optional[str]:
        """Prevent synchronous run for AsyncNode."""
        raise RuntimeError(f"AsyncNode {self.__class__.__name__} must be run with run_async().")


class AsyncBatchNode(AsyncNode, BatchNode):  # type: ignore[misc]
    """Asynchronous version of BatchNode. Processes items sequentially but asynchronously."""

    async def _exec(self: "AsyncBatchNode", items: Optional[TypingIterable[Any]]) -> list[Any]:  # type: ignore[override]
        """Asynchronously execute each item in the batch."""
        if items is None:
            return []
        return [await super(AsyncBatchNode, self)._exec(item) for item in items]


class AsyncParallelBatchNode(AsyncNode, BatchNode):  # type: ignore[misc]
    """Asynchronous BatchNode that processes items in parallel using asyncio.gather."""

    async def _exec(self: "AsyncParallelBatchNode", items: Optional[TypingIterable[Any]]) -> list[Any]:  # type: ignore[override]
        """Asynchronously execute all items in the batch in parallel."""
        if items is None:
            return []
        tasks = [super(AsyncParallelBatchNode, self)._exec(item) for item in items]
        return await asyncio.gather(*tasks)


class AsyncFlow(Flow, AsyncNode):  # type: ignore[misc]
    """Asynchronous version of Flow."""

    async def _orch_async(
        self: "AsyncFlow", shared: dict[str, Any], params: Optional[dict[str, Any]] = None
    ) -> Optional[str]:
        """Orchestrate internal asynchronous logic."""
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
                raise TypeError(f"Node {current_node.__class__.__name__} is not a recognized Node type.")
            current_node = copy.copy(self.get_next_node(current_node, last_action))
        return last_action

    async def _run_async(self: "AsyncFlow", shared: dict[str, Any]) -> Optional[str]:  # type: ignore[override]
        """Run internal asynchronous method for the flow."""
        prep_result: Any = await self.prep_async(shared)
        orch_result: Optional[str] = await self._orch_async(shared)
        return await self.post_async(shared, prep_result, orch_result)

    async def post_async(  # noqa: ANN401
        self: "AsyncFlow",
        shared: dict[str, Any],
        prep_res: Any,  # noqa: ANN401
        exec_res: Optional[str],  # noqa: ANN401
    ) -> Optional[str]:
        """Post-process asynchronously the entire flow.

        By default, returns the execution result of the orchestration (last action).
        Subclasses can override this.
        """
        return exec_res


class AsyncBatchFlow(AsyncFlow, BatchFlow):  # type: ignore[misc]
    """Asynchronous BatchFlow. Runs the async sub-flow for each item sequentially."""

    async def _run_async(self: "AsyncBatchFlow", shared: dict[str, Any]) -> None:  # type: ignore[override]
        """Asynchronously run the sub-flow for each item in the batch."""
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
        """Asynchronously run the sub-flow for each item in parallel using asyncio.gather."""
        batch_params_iterable: Optional[TypingIterable[dict[str, Any]]] = await self.prep_async(shared)
        if batch_params_iterable is None:
            batch_params_iterable = []

        tasks = []
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            tasks.append(self._orch_async(shared, current_run_params))

        await asyncio.gather(*tasks)
        await self.post_async(shared, batch_params_iterable, None)


# End of src/sourcelens/core/flow_engine.py
