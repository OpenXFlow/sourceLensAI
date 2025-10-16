# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Synchronous core of the PocketFlow-like workflow engine for SourceLens.

This module provides classes for defining synchronous nodes (individual steps)
and flows (sequences of nodes) to orchestrate complex tasks. It supports
batch processing, retries, and conditional transitions for synchronous operations.
This version introduces generic types for better type safety between P-E-P stages
and uses more descriptive method names for node lifecycle phases.
"""

import abc
import copy
import time
import warnings
from collections.abc import Iterable as TypingIterable
from typing import Any, Generic, Optional, TypeVar

from sourcelens.utils._exceptions import LlmApiError

# --- Type Variables for Generics ---
SharedContextType = TypeVar("SharedContextType", bound=dict[str, Any])
"""Type variable representing the structure of the shared context dictionary."""

PreparedInputsType = TypeVar("PreparedInputsType")
"""Type variable representing the result type of the 'pre_execution' method."""

ExecutionResultType = TypeVar("ExecutionResultType")
"""Type variable representing the result type of the 'execution' method."""

ItemType = TypeVar("ItemType")
"""Type variable representing the type of a single item in a batch."""

BatchItemExecutionResultType = TypeVar("BatchItemExecutionResultType")
"""Type variable representing the result type of 'execution' for a single item in a batch."""

FlowPreparedInputsType = TypeVar("FlowPreparedInputsType", default=None)  # type: ignore[type_var_default]


class BaseNode(Generic[SharedContextType, PreparedInputsType, ExecutionResultType]):
    """Base class for all synchronous nodes in a workflow, using generic types
    and descriptive phase method names.

    This class is generic over `SharedContextType` (type of shared data),
    `PreparedInputsType` (result of pre-execution phase), and
    `ExecutionResultType` (result of execution phase).
    """

    def __init__(self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]") -> None:
        """Initialize a BaseNode, setting up parameters and successors storage."""
        self.params: dict[str, Any] = {}
        self.successors: dict[str, BaseNode[Any, Any, Any]] = {}

    def set_params(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]", params: dict[str, Any]
    ) -> None:
        """Set parameters that can be used by the node during its lifecycle.

        Args:
            params: A dictionary of parameters.
        """
        self.params = params

    def next(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]",
        node: "BaseNode[Any, Any, Any]",
        action: str = "default",
    ) -> "BaseNode[Any, Any, Any]":
        """Define the next node in the flow for a given action.

        This method allows chaining nodes together to form a sequence or graph
        of operations. The `action` parameter enables conditional branching.

        Args:
            node: The successor node to transition to.
            action: The action string that triggers the transition to this
                    successor node. Defaults to "default" for unconditional
                    transitions.

        Returns:
            The successor node, allowing for fluent API chaining (e.g.,
            `node1.next(node2).next(node3)`).
        """
        if action in self.successors:
            warnings.warn(
                f"Overwriting successor for action '{action}' in node {self.__class__.__name__}", stacklevel=2
            )
        self.successors[action] = node
        return node

    @abc.abstractmethod
    def pre_execution(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]", shared_context: SharedContextType
    ) -> PreparedInputsType:
        """Prepare input data for the main execution phase.

        Subclasses must implement this method. This phase typically involves
        extracting and transforming data from the `shared_context` to prepare
        the necessary inputs for the `execution` method.

        Args:
            shared_context: The shared context dictionary, containing data
                            from previous nodes or initial setup.

        Returns:
            Data prepared for the `execution` method, of type `PreparedInputsType`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement the 'pre_execution' method.")

    @abc.abstractmethod
    def execution(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]",
        prepared_inputs: PreparedInputsType,
    ) -> ExecutionResultType:
        """Execute the core logic of the node.

        Subclasses must implement this method. This is the main processing task
        of the node, operating on the `prepared_inputs` from the `pre_execution` phase.

        Args:
            prepared_inputs: The data prepared by the `pre_execution` method.

        Returns:
            The result of the node's execution, of type `ExecutionResultType`.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement the 'execution' method.")

    @abc.abstractmethod
    def post_execution(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]",
        shared_context: SharedContextType,
        prepared_inputs: PreparedInputsType,
        execution_outputs: ExecutionResultType,
    ) -> Optional[str]:
        """Update the shared context with results and determine the next flow action.

        Subclasses must implement this method. This phase handles the results of the
        `execution` method, typically by updating the `shared_context` with
        `execution_outputs`. It can also use `prepared_inputs` for context.
        The returned string determines which successor node a `Flow` will transition to.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: The data from the `pre_execution` phase.
            execution_outputs: The result from the `execution` phase.

        Returns:
            An optional action string. If None or "default", the "default"
            successor is chosen by the `Flow`. Other strings can trigger
            conditional branches.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement the 'post_execution' method.")

    def _execution_internal(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]",
        prepared_inputs: PreparedInputsType,
    ) -> ExecutionResultType:
        """Wrap internal main execution logic.

        This method is called by `_run_node_lifecycle` and is intended to be
        overridden by subclasses like `Node` to add features like retry logic.

        Args:
            prepared_inputs: The data from the `pre_execution` phase.

        Returns:
            The result of the node's execution.
        """
        return self.execution(prepared_inputs)

    def _run_node_lifecycle(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]", shared_context: SharedContextType
    ) -> Optional[str]:
        """Orchestrate the node's lifecycle: pre_execution, execution, post_execution.

        This method is typically called by a `Flow` to execute the node as part
        of a larger workflow.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            The action string returned by the `post_execution` method, used by
            `Flow` for determining the next node.
        """
        prepared_data: PreparedInputsType = self.pre_execution(shared_context)
        execution_result: ExecutionResultType = self._execution_internal(prepared_data)
        return self.post_execution(shared_context, prepared_data, execution_result)

    def run_standalone(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]", shared_context: SharedContextType
    ) -> Optional[str]:
        """Run the node's full lifecycle as a standalone operation.

        This method is primarily for testing or direct execution of a single node
        outside of a `Flow`. If successors are defined, a warning is issued as
        they will not be executed by this method.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            The action string returned by the `post_execution` method.
        """
        if self.successors:
            warnings.warn(
                f"Node {self.__class__.__name__} has successors defined but is being run standalone. "
                f"Successors will not be executed. Use a Flow to run a sequence of nodes.",
                stacklevel=2,
            )
        return self._run_node_lifecycle(shared_context)

    def __rshift__(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]",
        other: "BaseNode[Any, Any, Any]",
    ) -> "BaseNode[Any, Any, Any]":
        """Define the default next node using the `>>` operator.

        This is syntactic sugar for `self.next(other, "default")`.

        Args:
            other: The next node in the default sequence.

        Returns:
            The `other` node, allowing for chaining.
        """
        return self.next(other)

    def __sub__(
        self: "BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]", action: str
    ) -> "_ConditionalTransition[SharedContextType, PreparedInputsType, ExecutionResultType]":
        """Initiate a conditional transition definition using the `-` operator.

        Example:
            `node1 - "on_failure" >> failure_handler_node`

        Args:
            action: The action string that will trigger this conditional transition.

        Returns:
            A `_ConditionalTransition` helper object.

        Raises:
            TypeError: If `action` is not a string.
        """
        if isinstance(action, str):
            return _ConditionalTransition(self, action)
        raise TypeError(f"Action for conditional transition must be a string, got {type(action).__name__}")


class _ConditionalTransition(Generic[SharedContextType, PreparedInputsType, ExecutionResultType]):
    """Helper class for defining conditional transitions using `node - "action" >> next_node` syntax."""

    def __init__(
        self: "_ConditionalTransition[SharedContextType, PreparedInputsType, ExecutionResultType]",
        src_node: BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType],
        action: str,
    ) -> None:
        """Initialize a conditional transition.

        Args:
            src_node: The source node of this transition.
            action: The action string that triggers this transition.
        """
        self.source_node: BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType] = src_node
        self.action: str = action

    def __rshift__(
        self: "_ConditionalTransition[SharedContextType, PreparedInputsType, ExecutionResultType]",
        target_node: BaseNode[Any, Any, Any],
    ) -> BaseNode[Any, Any, Any]:
        """Complete the conditional transition by specifying the target node.

        This is called when `>> target_node` is used after `source_node - "action"`.

        Args:
            target_node: The node to transition to if the action matches.

        Returns:
            The `target_node`, allowing for potential further chaining from it.
        """
        return self.source_node.next(target_node, self.action)


class Node(BaseNode[SharedContextType, PreparedInputsType, ExecutionResultType]):
    """A synchronous node with built-in retry logic for its main `execution` phase."""

    def __init__(
        self: "Node[SharedContextType, PreparedInputsType, ExecutionResultType]",
        max_retries: int = 1,
        wait: int = 0,
    ) -> None:
        """Initialize a Node with retry parameters.

        Args:
            max_retries: Maximum number of execution attempts for the `execution`
                         phase. Defaults to 1 (no actual retries).
            wait: Time in seconds to wait between retries. Defaults to 0.
        """
        super().__init__()
        self.max_retries: int = max(1, max_retries)
        self.wait: int = wait

    def execution_fallback(
        self: "Node[SharedContextType, PreparedInputsType, ExecutionResultType]",
        prepared_inputs: PreparedInputsType,
        exc: Exception,
    ) -> ExecutionResultType:
        """Handle fallback logic if all `execution` attempts fail.

        The default behavior is to re-raise the last encountered exception.
        Subclasses can override this to implement custom fallback actions,
        such as returning a default value or logging a more specific error.

        Args:
            prepared_inputs: The data from the `pre_execution` phase, which was
                             passed to the failed `execution` attempts.
            exc: The exception that occurred during the final execution attempt.

        Returns:
            A fallback result of type `ExecutionResultType`.

        Raises:
            Exception: Re-raises the input exception `exc` by default.
        """
        raise exc

    def _execution_internal(
        self: "Node[SharedContextType, PreparedInputsType, ExecutionResultType]",
        prepared_inputs: PreparedInputsType,
    ) -> ExecutionResultType:
        """Wrap the main `execution` logic with a retry mechanism.

        This method attempts to call `self.execution()` up to `self.max_retries`
        times. If all attempts fail due to recoverable errors, it then calls
        `self.execution_fallback()`.

        Args:
            prepared_inputs: The data from the `pre_execution` phase.

        Returns:
            The result from a successful `execution` call or from `execution_fallback`.
        """
        last_exception: Optional[Exception] = None
        recoverable_errors: tuple[type[Exception], ...] = (
            ValueError,
            TypeError,
            KeyError,
            FileNotFoundError,
            ConnectionError,
            OSError,
            AttributeError,
            IndexError,
            LlmApiError,
        )
        for current_retry_attempt in range(self.max_retries):
            try:
                return self.execution(prepared_inputs)
            except recoverable_errors as e_specific:
                last_exception = e_specific
                if current_retry_attempt == self.max_retries - 1:
                    break
                if self.wait > 0:
                    warn_msg_l1 = (
                        f"Node {self.__class__.__name__} failed on attempt "
                        f"{current_retry_attempt + 1}/{self.max_retries}"
                    )
                    warn_msg_l2 = (
                        f" with {type(e_specific).__name__}. Retrying after {self.wait}s. Error: {e_specific!s}"
                    )
                    warnings.warn(warn_msg_l1 + warn_msg_l2, stacklevel=2)
                    time.sleep(self.wait)
        if last_exception is None:
            # This path should ideally not be taken if execution always raises on error.
            # It's a safeguard for unexpected scenarios.
            last_exception = RuntimeError(
                f"Node {self.__class__.__name__} completed retries without success or caught exception."
            )
        return self.execution_fallback(prepared_inputs, last_exception)


class BatchNode(Node[SharedContextType, TypingIterable[ItemType], list[BatchItemExecutionResultType]]):
    """A synchronous node that processes a batch of items.

    The main `execution` method (inherited from `Node` and wrapped with its retry logic)
    should be implemented by subclasses to iterate over `items_iterable` (which is
    `prepared_inputs` for this class) and process each item.

    If retry logic is needed for *each individual item* within the batch,
    it must be implemented inside the subclass's `execution` method. The
    retry mechanism provided by the parent `Node` class applies to the
    batch processing as a whole.
    """

    @abc.abstractmethod
    def execution(  # type: ignore[override]
        self: "BatchNode[SharedContextType, TypingIterable[ItemType], list[BatchItemExecutionResultType]]",
        items_iterable: TypingIterable[ItemType],
    ) -> list[BatchItemExecutionResultType]:
        """Execute core logic for all items in the batch.

        Subclasses must implement this method to iterate through `items_iterable`
        and process each `ItemType`. The retry logic inherited from the `Node`
        class applies to this entire batch operation. If per-item retry is
        required, it needs to be handled within this method's implementation,
        for example, by calling a helper method for single item processing
        that includes its own retry/fallback mechanism.

        Args:
            items_iterable: The iterable of items from the `pre_execution` phase.

        Returns:
            A list of execution results, one for each processed item.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement 'execution' to process the batch of items."
        )

    def execution_fallback(  # type: ignore[override]
        self: "BatchNode[SharedContextType, TypingIterable[ItemType], list[BatchItemExecutionResultType]]",
        items_iterable: TypingIterable[ItemType],
        exc: Exception,
    ) -> list[BatchItemExecutionResultType]:
        """Handle fallback logic if the entire batch processing (`execution`) fails all retries.

        Args:
            items_iterable: The original iterable of items passed to `execution`.
            exc: The exception that caused the batch processing to fail.

        Returns:
            A list of fallback results (e.g., error markers for each item),
            or re-raises the exception by default.

        Raises:
            Exception: Re-raises `exc` by default.
        """
        # Example of a more graceful fallback:
        # error_marker = BatchItemExecutionResultType() # Assuming a way to create an error marker
        # return [error_marker for _ in items_iterable]
        raise exc


class Flow(BaseNode[SharedContextType, FlowPreparedInputsType, Optional[str]]):
    """Orchestrates the synchronous execution of a sequence of connected nodes."""

    def __init__(
        self: "Flow[SharedContextType, FlowPreparedInputsType]",
        start: Optional[BaseNode[Any, Any, Any]] = None,
    ) -> None:
        """Initialize a Flow.

        Args:
            start: The starting node of the flow. This node will be the first
                   one executed when the flow runs. It can also be set later
                   using the `start_with` method.
        """
        super().__init__()
        self.start_node: Optional[BaseNode[Any, Any, Any]] = start

    def start_with(
        self: "Flow[SharedContextType, FlowPreparedInputsType]",
        start_node: BaseNode[Any, Any, Any],
    ) -> BaseNode[Any, Any, Any]:
        """Set the starting node of the flow.

        Args:
            start_node: The node to start the flow execution from.

        Returns:
            The `start_node`, allowing for chaining (e.g., `flow.start_with(node_a) >> node_b`).
        """
        self.start_node = start_node
        return start_node

    def pre_execution(  # type: ignore[override]
        self: "Flow[SharedContextType, FlowPreparedInputsType]", shared_context: SharedContextType
    ) -> FlowPreparedInputsType:
        """Prepare for the flow execution (typically a no-op for the Flow itself).

        This method is called before the Flow begins orchestrating its child nodes.
        Subclasses can override this to perform setup specific to the Flow's operation.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            The prepared inputs for the Flow's `execution` phase. Defaults to
            `None` as `FlowPreparedInputsType` defaults to `None`.
        """
        del shared_context  # Mark as unused if no logic is performed with it
        return None  # type: ignore[return-value]

    def execution(  # type: ignore[override]
        self: "Flow[SharedContextType, FlowPreparedInputsType]", prepared_flow_inputs: FlowPreparedInputsType
    ) -> Optional[str]:
        """Execute phase for the Flow itself (typically triggers orchestration).

        The primary execution logic (running child nodes) is handled by `_orchestrate`,
        which is called from `_run_node_lifecycle`. This method is part of the
        `BaseNode` interface but its direct utility for `Flow` is limited as the
        orchestration is the core "execution".

        Args:
            prepared_flow_inputs: The result from this Flow's `pre_execution` method.

        Returns:
            None by default. The actual outcome (last action from child nodes)
            is determined by the orchestration process.

        Raises:
            NotImplementedError: As direct call is not the intended use.
        """
        del prepared_flow_inputs
        raise NotImplementedError(
            "Flow.execution should not be called directly. Orchestration occurs within _run_node_lifecycle."
        )

    def post_execution(  # type: ignore[override]
        self: "Flow[SharedContextType, FlowPreparedInputsType]",
        shared_context: SharedContextType,
        prepared_flow_inputs: FlowPreparedInputsType,
        orchestration_result: Optional[str],
    ) -> Optional[str]:
        """Post-process the entire flow's execution.

        This method is called after the Flow has finished orchestrating all its
        child nodes.

        Args:
            shared_context: The shared context dictionary.
            prepared_flow_inputs: The result from this Flow's `pre_execution` phase.
            orchestration_result: The action string returned by the last executed
                                 node in the flow's sequence, or `None` if the
                                 flow did not complete or had no action.

        Returns:
            The `orchestration_result` by default, which can be used if this
            Flow is a sub-flow within another Flow.
        """
        del shared_context, prepared_flow_inputs
        return orchestration_result

    def get_next_node(
        self: "Flow[SharedContextType, FlowPreparedInputsType]",
        current_node: BaseNode[Any, Any, Any],
        action: Optional[str],
    ) -> Optional[BaseNode[Any, Any, Any]]:
        """Determine the next node in the flow based on the last action.

        Args:
            current_node: The node that has just finished its execution.
            action: The action string returned by `current_node.post_execution()`.

        Returns:
            The next `BaseNode` to execute, or `None` if the flow should terminate
            or no successor is defined for the given action.
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
            warning_text_l1 = f"Flow ends: Action '{resolved_action}' returned by {current_node.__class__.__name__}"
            warning_text_l2 = f" not found in defined successors: {list(current_node.successors.keys())}"
            warnings.warn(warning_text_l1 + warning_text_l2, stacklevel=2)
        return next_node

    def _orchestrate(
        self: "Flow[SharedContextType, FlowPreparedInputsType]",
        shared_context: SharedContextType,
        flow_runtime_params: Optional[dict[str, Any]],
    ) -> Optional[str]:
        """Orchestrate the execution of the sequence of nodes within this flow.

        Args:
            shared_context: The shared context dictionary passed through nodes.
            flow_runtime_params: Parameters specific to this run of the flow,
                                 combined with the Flow's own `self.params`.

        Returns:
            The action string returned by the last executed node in the flow,
            or `None` if the flow did not start or completed without a final action.
        """
        if not self.start_node:
            warnings.warn("Flow has no start node defined. Nothing to execute.", stacklevel=2)
            return None
        current_node: Optional[BaseNode[Any, Any, Any]] = copy.copy(self.start_node)
        effective_params: dict[str, Any] = {**self.params, **(flow_runtime_params or {})}
        last_action: Optional[str] = None
        while current_node:
            current_node.set_params(effective_params)
            last_action = current_node._run_node_lifecycle(shared_context)
            next_node_candidate = self.get_next_node(current_node, last_action)
            current_node = copy.copy(next_node_candidate) if next_node_candidate else None
        return last_action

    def _run_node_lifecycle(  # type: ignore[override]
        self: "Flow[SharedContextType, FlowPreparedInputsType]", shared_context: SharedContextType
    ) -> Optional[str]:
        """Execute the full lifecycle of this Flow node.

        For a `Flow`, the "execution" phase *is* the orchestration of its child nodes.
        This method calls `pre_execution`, then `_orchestrate` (which is the
        core work of the Flow), and finally `post_execution`.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            The result of the Flow's `post_execution` method, which is typically
            the action string from the last orchestrated child node.
        """
        prepared_flow_data: FlowPreparedInputsType = self.pre_execution(shared_context)
        # The "execution_outputs" for a Flow node is the result of orchestrating its children.
        orchestration_outputs: Optional[str] = self._orchestrate(shared_context, self.params)
        return self.post_execution(shared_context, prepared_flow_data, orchestration_outputs)


class BatchFlow(Flow[SharedContextType, TypingIterable[dict[str, Any]]]):
    """A synchronous flow that processes a batch of items.

    The `pre_execution` method should be implemented to return an iterable where
    each item is a dictionary of parameters for one run of the sub-flow defined
    by this `BatchFlow`. The `_orchestrate` method (from the parent `Flow`)
    will be called for each set of parameters.
    """

    @abc.abstractmethod
    def pre_execution(  # type: ignore[override]
        self, shared_context: SharedContextType
    ) -> TypingIterable[dict[str, Any]]:
        """Prepare an iterable of parameter dictionaries for batch processing.

        Each dictionary in the returned iterable will be merged with the
        `BatchFlow`'s own `self.params` and used for one execution run
        of the sub-flow orchestrated by this `BatchFlow`.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            An iterable of dictionaries, each representing parameters for a sub-flow run.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement 'pre_execution' to yield batch parameters."
        )

    def execution(  # type: ignore[override]
        self, prepared_batch_inputs: TypingIterable[dict[str, Any]]
    ) -> Optional[str]:
        """Execute phase for BatchFlow (typically a no-op).

        The core batch execution logic is handled by `_run_node_lifecycle`,
        which iterates through `prepared_batch_inputs` and calls `_orchestrate`
        for each item.

        Args:
            prepared_batch_inputs: The iterable of parameter dictionaries from `pre_execution`.

        Returns:
            None, as results are typically aggregated or handled in `post_execution`.
        """
        del prepared_batch_inputs
        return None  # This method is effectively bypassed by the custom _run_node_lifecycle.

    def _run_node_lifecycle(  # type: ignore[override]
        self: "BatchFlow[SharedContextType]", shared_context: SharedContextType
    ) -> None:
        """Run the batch flow by orchestrating the sub-flow for each item.

        This method overrides the parent `Flow`'s lifecycle execution. It calls
        `pre_execution` to get batch parameters, then iterates through these,
        calling `_orchestrate` for each set of parameters to run the sub-flow.
        Finally, it calls `post_execution`. This method itself returns `None`
        as the concept of a single "action string" for the entire batch
        is not usually applicable.

        Args:
            shared_context: The shared context dictionary.
        """
        batch_params_iterable: TypingIterable[dict[str, Any]] = self.pre_execution(shared_context)
        # self.execution(batch_params_iterable) # This call is not standard for BatchFlow orchestration

        # aggregated_orch_results: list[Optional[str]] = [] # Kept if needed for sophisticated post_execution
        for batch_item_params in batch_params_iterable:
            current_run_params: dict[str, Any] = {**self.params, **batch_item_params}
            _ = self._orchestrate(
                shared_context, current_run_params
            )  # Result of item orchestration usually ignored here
            # aggregated_orch_results.append(last_action_for_item)

        # `prepared_inputs` for BatchFlow's post_execution is the iterable of params.
        # `execution_outputs` is conceptually None for the batch as a whole from this lifecycle method.
        self.post_execution(shared_context, batch_params_iterable, None)

    def post_execution(  # type: ignore[override]
        self: "BatchFlow[SharedContextType]",
        shared_context: SharedContextType,
        prepared_batch_params: TypingIterable[dict[str, Any]],
        # This will be None from BatchFlow._run_node_lifecycle(), as the "execution"
        # of BatchFlow itself (the iteration) doesn't produce a single action string.
        orchestration_result_for_batch: Optional[str],
    ) -> None:
        """Post-process the entire batch flow execution.

        This method is called after all items in the batch have been processed
        (i.e., after the sub-flow has been orchestrated for each item).
        Subclasses can override this to perform aggregation of results from
        `shared_context` or other finalization tasks.

        Args:
            shared_context: The shared context dictionary, potentially modified
                            by the execution of sub-flows for each batch item.
            prepared_batch_params: The iterable of parameter dictionaries that
                                   was returned by `pre_execution`.
            orchestration_result_for_batch: This will typically be `None` as passed
                                            from `_run_node_lifecycle`. The results
                                            of individual sub-flow orchestrations
                                            are usually managed via `shared_context`.
        """
        del shared_context, prepared_batch_params, orchestration_result_for_batch
        pass  # Default implementation does nothing.


# End of src/sourcelens/core/flow_engine_sync.py
