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

"""Synchronous core of the PocketFlow-like workflow engine for SourceLens.

This module provides classes for defining synchronous nodes (individual steps)
and flows (sequences of nodes) to orchestrate complex tasks. It supports
batch processing, retries, and conditional transitions for synchronous operations.
This version introduces generic types for better type safety between P-E-P stages.
"""

import abc
import copy
import time
import warnings
from collections.abc import Iterable as TypingIterable
from typing import Any, Generic, Optional, TypeVar

from sourcelens.utils._exceptions import LlmApiError  # Added import for LlmApiError

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

FlowPrepResType = TypeVar("FlowPrepResType", default=None)  # type: ignore[type_var_default]


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
        raise exc

    def _exec(self: "Node[SharedStateType, PrepResType, ExecResType]", prep_res: PrepResType) -> ExecResType:
        """Wrap internal execution with retry logic."""
        last_exception: Optional[Exception] = None
        # Added LlmApiError to recoverable_errors
        recoverable_errors: tuple[type[Exception], ...] = (
            ValueError,
            TypeError,
            KeyError,
            FileNotFoundError,
            ConnectionError,
            OSError,
            AttributeError,
            IndexError,
            LlmApiError,  # Added LlmApiError here
        )

        for current_retry_attempt in range(self.max_retries):
            try:
                return self.exec(prep_res)
            except recoverable_errors as e_specific:
                last_exception = e_specific
                if current_retry_attempt == self.max_retries - 1:
                    break
                if self.wait > 0:
                    warning_message_part1 = (
                        f"Node {self.__class__.__name__} failed on attempt "
                        f"{current_retry_attempt + 1}/{self.max_retries} "
                        f"with {type(e_specific).__name__}."
                    )
                    warning_message_part2 = f" Retrying after {self.wait}s. Error: {e_specific!s}"
                    warnings.warn(warning_message_part1 + warning_message_part2, stacklevel=2)
                    time.sleep(self.wait)

        if last_exception is None:
            # This case should ideally not be reached if exec always raises on failure
            # or if the loop completes without any caught exceptions (which means success).
            # However, as a safeguard:
            last_exception = RuntimeError(
                f"Node {self.__class__.__name__} completed all retries without success or a caught exception."
            )
        return self.exec_fallback(prep_res, last_exception)


class BatchNode(Node[SharedStateType, TypingIterable[ItemType], list[BatchExecResType]]):
    """A synchronous node that processes a batch of items.

    `prep` should return an iterable of `ItemType`.
    `exec` (when implemented in subclass) should process a single `ItemType` and return `BatchExecResType`.
    `post` will receive the original iterable and a list of `BatchExecResType`.
    """

    def _exec(self, items_iterable: TypingIterable[ItemType]) -> list[BatchExecResType]:
        """Wrap internal execution for batch processing.

        Args:
            items_iterable: An iterable of items returned by `prep`.

        Returns:
            A list of execution results, one for each item.

        """
        results: list[BatchExecResType] = []
        for item in items_iterable:
            # For BatchNode, super()._exec calls Node._exec for each item,
            # which includes the retry logic.
            results.append(super()._exec(item))  # type: ignore[arg-type]
        return results


class Flow(BaseNode[SharedStateType, FlowPrepResType, Optional[str]]):
    """Orchestrates the synchronous execution of a sequence of connected nodes."""

    def __init__(
        self: "Flow[SharedStateType, FlowPrepResType]",
        start: Optional[BaseNode[Any, Any, Any]] = None,
    ) -> None:
        """Initialize a Flow.

        Args:
            start: The starting node of the flow. Can also be set later.
        """
        # This print is for debugging purposes to ensure the correct file version is loaded.
        super().__init__()
        self.start_node: Optional[BaseNode[Any, Any, Any]] = start

    def start(
        self: "Flow[SharedStateType, FlowPrepResType]",
        start_node: BaseNode[Any, Any, Any],
    ) -> BaseNode[Any, Any, Any]:
        """Set the starting node of the flow.

        Args:
            start_node: The node to start the flow execution from.

        Returns:
            The `start_node`, allowing for chaining.
        """
        self.start_node = start_node
        return start_node

    def prep(self: "Flow[SharedStateType, FlowPrepResType]", shared: SharedStateType) -> FlowPrepResType:
        """Prepare for the flow execution (typically a no-op for the Flow itself).

        Args:
            shared: The shared state dictionary.

        Returns:
            Returns None by default as FlowPrepResType defaults to None.
            Subclasses can override this to perform setup specific to the Flow.
        """
        del shared  # Mark as unused if no logic is performed with it
        return None  # type: ignore[return-value]

    def exec(self: "Flow[SharedStateType, FlowPrepResType]", prep_res: FlowPrepResType) -> Optional[str]:
        """Execute phase for the Flow itself (typically a no-op).

        The primary execution logic (running child nodes) is in `_orch`.

        Args:
            prep_res: The result from this Flow's `prep` method.

        Returns:
            None by default. The actual outcome is determined by `_orch`.
        """
        del prep_res  # Mark as unused
        return None

    def post(
        self: "Flow[SharedStateType, FlowPrepResType]",
        shared: SharedStateType,
        prep_res: FlowPrepResType,
        exec_res: Optional[str],
    ) -> Optional[str]:
        """Post-process the entire flow.

        Args:
            shared: The shared state dictionary.
            prep_res: The result from this Flow's `prep` method.
            exec_res: The result from the Flow's orchestration (last action from last node).

        Returns:
            The `exec_res` (last_action from orchestration) by default.
        """
        del shared, prep_res  # Mark as unused
        return exec_res

    def get_next_node(
        self: "Flow[SharedStateType, FlowPrepResType]",
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

        if not next_node and resolved_action != "default" and "default" in current_node.successors:
            warnings.warn(
                f"Action '{resolved_action}' not found for {current_node.__class__.__name__}. "
                f"Falling back to 'default' successor.",
                stacklevel=2,
            )
            next_node = current_node.successors.get("default")
        elif not next_node and current_node.successors and resolved_action != "default":
            # Only warn if there were *some* successors defined but not for the specific action
            warnings.warn(
                f"Flow ends: Action '{resolved_action}' returned by {current_node.__class__.__name__} "
                f"not found in its defined successors: {list(current_node.successors.keys())}",
                stacklevel=2,
            )
        return next_node

    def _orch(
        self: "Flow[SharedStateType, FlowPrepResType]",
        shared: SharedStateType,
        params: Optional[dict[str, Any]],
    ) -> Optional[str]:
        """Orchestrate internal logic for running the synchronous flow.

        Args:
            shared: The shared state dictionary.
            params: Parameters for the flow, combining self.params and any runtime params.

        Returns:
            The action string returned by the last executed node in the flow.
        """
        if not self.start_node:
            warnings.warn("Flow has no start node defined. Nothing to execute.", stacklevel=2)
            return None

        current_node: Optional[BaseNode[Any, Any, Any]] = copy.copy(self.start_node)
        flow_params_to_use: dict[str, Any] = params if params is not None else {**self.params}
        last_action: Optional[str] = None

        while current_node:
            current_node.set_params(flow_params_to_use)
            last_action = current_node._run(shared)
            next_node_candidate = self.get_next_node(current_node, last_action)
            # Deep copy the next node to ensure its state is isolated if the flow re-runs
            # or if the same node instance appears multiple times in a flow (though not typical for P-E-P).
            current_node = copy.copy(next_node_candidate) if next_node_candidate else None
        return last_action

    def _run(self: "Flow[SharedStateType, FlowPrepResType]", shared: SharedStateType) -> Optional[str]:
        """Run internal method for the synchronous flow."""
        # This print is for debugging purposes.
        prep_result: FlowPrepResType = self.prep(shared)
        # The Flow's own exec is usually a no-op; _orch handles child node execution.
        self.exec(prep_result)  # Call Flow's own exec method
        orch_result: Optional[str] = self._orch(shared, self.params)
        # The result of the orchestration (last_action) is passed to Flow's post method
        final_result = self.post(shared, prep_result, orch_result)
        # This print is for debugging purposes.
        return final_result


class BatchFlow(Flow[SharedStateType, TypingIterable[dict[str, Any]]]):
    """A synchronous flow that processes a batch of items.

    The `prep` method of this flow should return an iterable of dictionaries,
    where each dictionary contains parameters for one run of the sub-flow.
    The `post` method's `exec_res` will be `None` by default as results are per-item.
    """

    @abc.abstractmethod
    def prep(self, shared: SharedStateType) -> TypingIterable[dict[str, Any]]:  # type: ignore[override]
        """Prepare an iterable of parameter dictionaries for batch processing.

        Each dictionary in the iterable will be used as specific parameters
        for one execution run of the sub-flow defined by this BatchFlow.

        Args:
            shared: The shared state dictionary.

        Returns:
            An iterable of dictionaries, each representing parameters for a sub-flow run.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement 'prep' to yield batch parameters.")

    def exec(self, prep_res: TypingIterable[dict[str, Any]]) -> Optional[str]:  # type: ignore[override]
        """Execute phase for BatchFlow (typically a no-op).

        The core batch execution logic is handled by `_run`, which iterates
        through `prep_res` and calls `_orch` for each item.

        Args:
            prep_res: The iterable of parameter dictionaries from `prep`.

        Returns:
            None, as results are aggregated or handled in `post`.
        """
        del prep_res  # Mark as unused
        return None

    def _run(self: "BatchFlow[SharedStateType]", shared: SharedStateType) -> None:
        """Run internal method for synchronous batch flow execution.

        Overrides Flow._run to iterate through batch items.
        The overall result of BatchFlow's _run is None, as individual
        results are handled by the sub-flow or aggregated in `post`.
        """
        batch_params_iterable: TypingIterable[dict[str, Any]] = self.prep(shared)
        # Call BatchFlow's own exec, which returns None.
        # The result of this is not directly used in the loop.
        self.exec(batch_params_iterable)  # type: ignore[arg-type]

        aggregated_orch_results: list[Optional[str]] = []
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            last_action_for_item: Optional[str] = self._orch(shared, current_run_params)
            aggregated_orch_results.append(last_action_for_item)

        # The third argument to post for BatchFlow should be consistent with Flow's exec result type (Optional[str])
        # Since BatchFlow's exec returns None, we pass None here. The actual results (if any)
        # are typically aggregated within the shared state or specific post-processing logic.
        self.post(shared, batch_params_iterable, None)

    def post(
        self: "BatchFlow[SharedStateType]",  # Adjusted self type
        shared: SharedStateType,
        prep_res: TypingIterable[dict[str, Any]],
        exec_res: Optional[str],  # This will be None from BatchFlow._run()
    ) -> None:  # BatchFlow's post typically does not return an action string.
        """Post-process the entire batch flow.

        Args:
            shared: The shared state dictionary.
            prep_res: The iterable of parameter dictionaries from `prep`.
            exec_res: The result from `BatchFlow.exec()`, which is None.
                      Individual item results are typically in `shared_state`
                      or handled by sub-flow's post methods.
        """
        # Default implementation does nothing. Subclasses can override to
        # perform aggregation or finalization based on batch_params_iterable
        # and changes made to shared_state during the execution of sub-flows.
        del shared, prep_res, exec_res  # Mark as unused
        pass


# End of src/sourcelens/core/flow_engine_sync.py
