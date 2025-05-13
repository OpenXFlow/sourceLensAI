# src/sourcelens/core/flow_engine_sync.py

"""Synchronous core of the PocketFlow-like workflow engine for SourceLens.

This module provides classes for defining synchronous nodes (individual steps)
and flows (sequences of nodes) to orchestrate complex tasks. It supports
batch processing, retries, and conditional transitions for synchronous operations.
This version introduces generic types for better type safety between P-E-P stages.
"""

import copy
import time
import warnings
from collections.abc import Iterable as TypingIterable
from typing import Any, Generic, Optional, TypeVar

# --- Type Variables for Generics ---
SharedStateType = TypeVar("SharedStateType", bound=dict[str, Any])
"""Type variable representing the structure of the shared state dictionary."""

PrepResType = TypeVar("PrepResType")
"""Type variable representing the result type of the 'prep' method."""

ExecResType = TypeVar("ExecResType")
"""Type variable representing the result type of the 'exec' method."""

ItemType = TypeVar("ItemType")
"""Type variable representing the type of a single item in a batch."""

BatchExecResType = TypeVar("BatchExecResType")
"""Type variable representing the result type of 'exec' for a single item in a batch."""


class BaseNode(Generic[SharedStateType, PrepResType, ExecResType]):
    """Base class for all synchronous nodes in a workflow, using generic types.

    This class is generic over `SharedStateType` (type of shared data),
    `PrepResType` (result of preparation phase), and `ExecResType` (result
    of execution phase).
    """

    def __init__(self: "BaseNode[SharedStateType, PrepResType, ExecResType]") -> None:
        """Initialize a BaseNode."""
        self.params: dict[str, Any] = {}
        self.successors: dict[str, BaseNode[Any, Any, Any]] = {}

    def set_params(self: "BaseNode[SharedStateType, PrepResType, ExecResType]", params: dict[str, Any]) -> None:
        """Set parameters for the node.

        Args:
            params: A dictionary of parameters.

        """
        self.params = params

    def next(
        self: "BaseNode[SharedStateType, PrepResType, ExecResType]",
        node: "BaseNode[Any, Any, Any]",
        action: str = "default",
    ) -> "BaseNode[Any, Any, Any]":
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

    def prep(self: "BaseNode[SharedStateType, PrepResType, ExecResType]", shared: SharedStateType) -> PrepResType:
        """Prepare input data for the execution phase.

        To be implemented by subclasses.

        Args:
            shared: The shared state dictionary, typed by `SharedStateType`.

        Returns:
            Data prepared for the `exec` method, of type `PrepResType`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        # Subclasses must override this method.
        # Raising NotImplementedError is more appropriate than returning None with type ignore.
        raise NotImplementedError(f"{self.__class__.__name__} must implement the 'prep' method.")

    def exec(self: "BaseNode[SharedStateType, PrepResType, ExecResType]", prep_res: PrepResType) -> ExecResType:
        """Execute the core logic of the node.

        To be implemented by subclasses.

        Args:
            prep_res: The result returned by the `prep` method, of type `PrepResType`.

        Returns:
            The result of the node's execution, of type `ExecResType`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement the 'exec' method.")

    def post(
        self: "BaseNode[SharedStateType, PrepResType, ExecResType]",
        shared: SharedStateType,
        prep_res: PrepResType,
        exec_res: ExecResType,
    ) -> Optional[str]:
        """Update the shared state with the execution results.

        To be implemented by subclasses.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The result returned by the `prep` method.
            exec_res: The result returned by the `exec` method.

        Returns:
            An optional action string to determine the next node in a Flow.
            If None or "default" is returned, the "default" successor is chosen.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement the 'post' method.")

    def _exec(self: "BaseNode[SharedStateType, PrepResType, ExecResType]", prep_res: PrepResType) -> ExecResType:
        """Wrap internal execution."""
        return self.exec(prep_res)

    def _run(self: "BaseNode[SharedStateType, PrepResType, ExecResType]", shared: SharedStateType) -> Optional[str]:
        """Orchestrate internal run: prep, exec, and post.

        Args:
            shared: The shared state dictionary.

        Returns:
            The action string returned by the `post` method.

        """
        prep_result: PrepResType = self.prep(shared)
        exec_result: ExecResType = self._exec(prep_result)
        return self.post(shared, prep_result, exec_result)

    def run(self: "BaseNode[SharedStateType, PrepResType, ExecResType]", shared: SharedStateType) -> Optional[str]:
        """Run the node's prep, exec, and post methods.

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

    def __rshift__(
        self: "BaseNode[SharedStateType, PrepResType, ExecResType]", other: "BaseNode[Any, Any, Any]"
    ) -> "BaseNode[Any, Any, Any]":
        """Syntactic sugar for `self.next(other, "default")`."""
        return self.next(other)

    def __sub__(
        self: "BaseNode[SharedStateType, PrepResType, ExecResType]", action: str
    ) -> "_ConditionalTransition[SharedStateType, PrepResType, ExecResType]":
        """Start a conditional transition definition."""
        if isinstance(action, str):
            return _ConditionalTransition(self, action)
        raise TypeError(f"Action for conditional transition must be a string, got {type(action).__name__}")


class _ConditionalTransition(Generic[SharedStateType, PrepResType, ExecResType]):
    """Helper class for defining conditional transitions using the '-' operator."""

    def __init__(
        self: "_ConditionalTransition[SharedStateType, PrepResType, ExecResType]",
        src_node: BaseNode[SharedStateType, PrepResType, ExecResType],
        action: str,
    ) -> None:
        """Initialize a _ConditionalTransition.

        Args:
            src_node: The source node of the transition.
            action: The action string.

        """
        self.source_node: BaseNode[SharedStateType, PrepResType, ExecResType] = src_node
        self.action: str = action

    def __rshift__(
        self: "_ConditionalTransition[SharedStateType, PrepResType, ExecResType]", target_node: BaseNode[Any, Any, Any]
    ) -> BaseNode[Any, Any, Any]:
        """Complete the conditional transition by defining the target node.

        Args:
            target_node: The target node for this conditional transition.

        Returns:
            The target_node, allowing for further chaining if needed.

        """
        return self.source_node.next(target_node, self.action)


class Node(BaseNode[SharedStateType, PrepResType, ExecResType]):
    """A synchronous node with built-in retry logic for its execution phase."""

    def __init__(self: "Node[SharedStateType, PrepResType, ExecResType]", max_retries: int = 1, wait: int = 0) -> None:
        """Initialize a Node with retry parameters.

        Args:
            max_retries: Maximum number of execution attempts (default is 1, meaning no retries).
            wait: Time in seconds to wait between retries (default is 0).

        """
        super().__init__()
        self.max_retries: int = max(1, max_retries)
        self.wait: int = wait

    def exec_fallback(
        self: "Node[SharedStateType, PrepResType, ExecResType]", prep_res: PrepResType, exc: Exception
    ) -> ExecResType:
        """Handle fallback logic if all execution retries fail.

        Args:
            prep_res: The result from the `prep` method.
            exc: The exception that occurred during the last execution attempt.

        Returns:
            A fallback result of type `ExecResType`.

        Raises:
            Exception: Re-raises the input exception `exc` by default.

        """
        raise exc  # This is the default, subclasses might return ExecResType

    def _exec(self: "Node[SharedStateType, PrepResType, ExecResType]", prep_res: PrepResType) -> ExecResType:  # type: ignore[override]
        """Wrap internal execution with retry logic."""
        last_exception: Optional[Exception] = None
        for current_retry_attempt in range(self.max_retries):
            try:
                # Calls exec of the concrete subclass which should return ExecResType
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
        # exec_fallback should return ExecResType or raise
        return self.exec_fallback(prep_res, fallback_exc)


class BatchNode(Node[SharedStateType, TypingIterable[ItemType], list[BatchExecResType]]):
    """A synchronous node that processes a batch of items.

    `prep` should return an iterable of `ItemType`.
    `exec` (when implemented in subclass) should process a single `ItemType` and return `BatchExecResType`.
    `post` will receive the original iterable and a list of `BatchExecResType`.
    """

    # Concrete BatchNode subclass must implement:
    # def prep(self, shared: SharedStateType) -> TypingIterable[ItemType]: ...
    # def exec(self, item: ItemType) -> BatchExecResType: ...
    # def post(
    #     self,
    #     shared: SharedStateType,
    #     prep_res: TypingIterable[ItemType],
    #     exec_res_list: list[BatchExecResType]
    # ) -> Optional[str]: ...
    # Note: The line length for the post signature above was an issue (E501)

    def _exec(self, items: Optional[TypingIterable[ItemType]]) -> list[BatchExecResType]:  # type: ignore[override]
        """Wrap internal execution for batch processing.

        Args:
            items: An iterable of items returned by `prep`.

        Returns:
            A list of execution results, one for each item.

        """
        if items is None:
            return []
        results: list[BatchExecResType] = []
        for item in items:
            # super() correctly calls Node._exec(item)
            # Node._exec calls self.exec(item), where self.exec is the one
            # implemented by the concrete BatchNode subclass taking ItemType.
            results.append(super()._exec(item))  # type: ignore[arg-type] # item is ItemType, Node._exec expects PrepResType
            # This works because BatchNode's PrepResType is Iterable[ItemType]
            # and Node._exec is called with a single ItemType, which is correct
            # for the user-defined exec(item: ItemType)
        return results


class Flow(BaseNode[SharedStateType, PrepResType, ExecResType]):
    """Orchestrates the synchronous execution of a sequence of connected nodes."""

    def __init__(
        self: "Flow[SharedStateType, PrepResType, ExecResType]", start: Optional[BaseNode[Any, Any, Any]] = None
    ) -> None:
        """Initialize a Flow.

        Args:
            start: The starting node of the flow. Can also be set later.

        """
        super().__init__()
        self.start_node: Optional[BaseNode[Any, Any, Any]] = start

    def start(
        self: "Flow[SharedStateType, PrepResType, ExecResType]", start_node: BaseNode[Any, Any, Any]
    ) -> BaseNode[Any, Any, Any]:
        """Set the starting node of the flow.

        Args:
            start_node: The node to start the flow execution from.

        Returns:
            The `start_node`, allowing for chaining.

        """
        self.start_node = start_node
        return start_node

    def get_next_node(
        self: "Flow[SharedStateType, PrepResType, ExecResType]",
        current_node: BaseNode[Any, Any, Any],
        action: Optional[str],
    ) -> Optional[BaseNode[Any, Any, Any]]:
        """Determine the next node based on the current node and its returned action.

        Args:
            current_node: The node that just finished execution.
            action: The action string returned by `current_node.post()`.

        Returns:
            The next node to execute, or None if the flow ends.

        """
        resolved_action: str = action if isinstance(action, str) else "default"
        next_node: Optional[BaseNode[Any, Any, Any]] = current_node.successors.get(resolved_action)

        if not next_node and current_node.successors:
            warnings.warn(
                f"Flow ends: Action '{resolved_action}' returned by {current_node.__class__.__name__} "
                f"not found in its defined successors: {list(current_node.successors.keys())}",
                stacklevel=2,
            )
        elif not next_node and not current_node.successors:
            pass

        return next_node

    def _orch(
        self: "Flow[SharedStateType, PrepResType, ExecResType]",
        shared: SharedStateType,
        params: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """Orchestrate internal logic for running the synchronous flow.

        Args:
            shared: The shared state dictionary.
            params: Initial parameters for the flow.

        Returns:
            The action string returned by the last executed node in the flow.

        """
        if not self.start_node:
            warnings.warn("Flow has no start node defined. Nothing to execute.", stacklevel=2)
            return None

        current_node: Optional[BaseNode[Any, Any, Any]] = copy.copy(self.start_node)
        flow_params: dict[str, Any] = params if params is not None else {**self.params}
        last_action: Optional[str] = None

        while current_node:
            current_node.set_params(flow_params)
            # Assuming current_node._run can handle the SharedStateType of this Flow.
            # If current_node has a more specific SharedStateType, it might be an issue,
            # but for now, we assume compatibility or that shared state is additive.
            last_action = current_node._run(shared)  # type: ignore[arg-type] # noqa: SLF001
            current_node = copy.copy(self.get_next_node(current_node, last_action))

        return last_action

    def _run(  # type: ignore[override]
        self: "Flow[SharedStateType, PrepResType, ExecResType]", shared: SharedStateType
    ) -> Optional[str]:
        """Run internal method for the synchronous flow."""
        prep_result: PrepResType = self.prep(shared)
        orch_result: Optional[str] = self._orch(shared)
        # Flow.post expects ExecResType as its exec_res, but _orch returns Optional[str].
        # If ExecResType for Flow is intended to be Optional[str], this is fine.
        return self.post(shared, prep_result, orch_result)  # type: ignore[arg-type]

    def post(  # type: ignore[override]
        self: "Flow[SharedStateType, PrepResType, ExecResType]",
        shared: SharedStateType,
        prep_res: PrepResType,
        exec_res: Optional[str],  # This is the last_action from _orch
    ) -> Optional[str]:
        """Post-process the entire synchronous flow.

        Args:
            shared: The shared state dictionary.
            prep_res: The result from this Flow's `prep` method.
            exec_res: The result from the Flow's orchestration (last action from last node).

        Returns:
            The `exec_res` (last_action from orchestration) by default.

        """
        return exec_res


class BatchFlow(Flow[SharedStateType, TypingIterable[dict[str, Any]], None]):
    """A synchronous flow that processes a batch of items.

    The `prep` method of this flow should return an iterable of dictionaries,
    where each dictionary contains parameters for one run of the sub-flow.
    The `post` method's `exec_res` will be `None` by default as results are per-item.
    """

    # User of BatchFlow typically implements:
    # def prep(self, shared: SharedStateType) -> TypingIterable[dict[str, Any]]: ...
    # def post(
    #     self,
    #     shared: SharedStateType,
    #     prep_res: TypingIterable[dict[str, Any]], # prep_res is iterable
    #     exec_res: None # exec_res for BatchFlow's post is None
    # ) -> Optional[str]: ...
    # Note: Above comment was E501

    def _run(self: "BatchFlow[SharedStateType]", shared: SharedStateType) -> None:  # type: ignore[override]
        """Run internal method for synchronous batch flow execution."""
        # prep_res_iterable: TypingIterable[dict[str, Any]]
        prep_res_iterable = self.prep(shared)  # prep returns TypingIterable[dict[str, Any]]

        if prep_res_iterable is None:  # Should not happen if prep is implemented correctly
            prep_res_iterable = []

        for batch_item_params in prep_res_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            self._orch(shared, current_run_params)  # _orch result (last_action) is not aggregated here

        # Pass the original iterable from prep and None as exec_res
        # BatchFlow's ExecResType is None, so post expects None.
        self.post(shared, prep_res_iterable, None)


# End of src/sourcelens/core/flow_engine_sync.py
