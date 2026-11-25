"""
Deterministic Workflow Validator (ContextIQ Phase 7.4).
Enforces:
1. Action Registration: Rejects unregistered action contracts.
2. DAG Integrity: Enforces acyclicity, reference validity, and topological ordering.
3. Parameter Conformance: Verifies required inputs and bounds.
4. Lifecycle State Invariants: Prevents invalid transitions and duplicate executions.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from app.schemas.workflow_schemas import (
    WorkflowDependencySchema,
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.services.action_registry import ActionRegistry


# Formal 13-State Permissible Transition Matrix (from Phase 7.1 Lifecycle Specification)
ALLOWED_TRANSITIONS: Dict[WorkflowLifecycleState, Set[WorkflowLifecycleState]] = {
    WorkflowLifecycleState.CREATED: {
        WorkflowLifecycleState.DRAFT,
        WorkflowLifecycleState.CANCELLED,
    },
    WorkflowLifecycleState.DRAFT: {
        WorkflowLifecycleState.VALIDATING,
        WorkflowLifecycleState.CANCELLED,
    },
    WorkflowLifecycleState.VALIDATING: {
        WorkflowLifecycleState.AWAITING_APPROVAL,
        WorkflowLifecycleState.APPROVED,  # Pre-authorized tier 0/1 policies
        WorkflowLifecycleState.FAILED,
        WorkflowLifecycleState.CANCELLED,
    },
    WorkflowLifecycleState.AWAITING_APPROVAL: {
        WorkflowLifecycleState.APPROVED,
        WorkflowLifecycleState.CANCELLED,
        WorkflowLifecycleState.EXPIRED,
    },
    WorkflowLifecycleState.APPROVED: {
        WorkflowLifecycleState.SCHEDULED,
        WorkflowLifecycleState.EXECUTING,
        WorkflowLifecycleState.CANCELLED,
    },
    WorkflowLifecycleState.SCHEDULED: {
        WorkflowLifecycleState.EXECUTING,
        WorkflowLifecycleState.CANCELLED,
        WorkflowLifecycleState.EXPIRED,
    },
    WorkflowLifecycleState.EXECUTING: {
        WorkflowLifecycleState.COMPLETED,
        WorkflowLifecycleState.PARTIALLY_COMPLETED,
        WorkflowLifecycleState.FAILED,
        WorkflowLifecycleState.CANCELLED,
    },
    WorkflowLifecycleState.PARTIALLY_COMPLETED: {
        WorkflowLifecycleState.ROLLED_BACK,
    },
    WorkflowLifecycleState.FAILED: {
        WorkflowLifecycleState.ROLLED_BACK,
    },
    WorkflowLifecycleState.COMPLETED: {
        WorkflowLifecycleState.ROLLED_BACK,  # User-initiated undo
    },
    WorkflowLifecycleState.CANCELLED: set(),
    WorkflowLifecycleState.EXPIRED: set(),
    WorkflowLifecycleState.ROLLED_BACK: set(),
}


class WorkflowValidationError(Exception):
    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.errors = errors or [message]


class WorkflowValidator:
    """Deterministic validation engine for multi-step workflow graphs."""

    @classmethod
    def validate_lifecycle_transition(
        cls,
        current_state: WorkflowLifecycleState,
        target_state: WorkflowLifecycleState,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether transitioning from current_state to target_state is permissible.
        """
        if current_state == target_state:
            return True, None

        allowed_targets = ALLOWED_TRANSITIONS.get(current_state, set())
        if target_state not in allowed_targets:
            return False, (
                f"Invalid state transition: Cannot transition from '{current_state.value}' "
                f"to '{target_state.value}'. Allowed targets: {[s.value for s in allowed_targets]}"
            )
        return True, None

    @classmethod
    def validate_workflow_structure(
        cls,
        steps: List[WorkflowStepSchema],
        dependencies: List[WorkflowDependencySchema],
    ) -> List[str]:
        """
        Validates that a workflow definition or plan satisfies all compile-time invariants:
        - Non-empty step list
        - Action identifiers are registered
        - Step keys are unique
        - Dependencies reference existing step keys
        - Graph is a Directed Acyclic Graph (DAG) with no cycles
        - Parameter schemas are valid
        """
        errors: List[str] = []

        if not steps:
            errors.append("Workflow must contain at least one step.")
            return errors

        # 1. Step key uniqueness and action registration
        step_keys: Set[str] = set()
        for idx, step in enumerate(steps):
            if not step.step_key:
                errors.append(f"Step at index {idx} has an empty step_key.")
                continue

            if step.step_key in step_keys:
                errors.append(f"Duplicate step_key '{step.step_key}' detected.")
            step_keys.add(step.step_key)

            # Check action registry
            if not ActionRegistry.is_registered(step.action_identifier):
                errors.append(
                    f"Step '{step.step_key}' specifies unregistered action identifier: '{step.action_identifier}'"
                )
            else:
                param_errors = ActionRegistry.validate_action_parameters(
                    step.action_identifier, step.parameters
                )
                errors.extend(param_errors)

        # 2. Dependency reference integrity
        for dep in dependencies:
            if dep.source_step_key not in step_keys:
                errors.append(
                    f"Dependency references non-existent source_step_key: '{dep.source_step_key}'"
                )
            if dep.target_step_key not in step_keys:
                errors.append(
                    f"Dependency references non-existent target_step_key: '{dep.target_step_key}'"
                )
            if dep.source_step_key == dep.target_step_key:
                errors.append(
                    f"Self-referential dependency detected on step '{dep.source_step_key}'"
                )

        # 3. Cycle Detection (Topological Sort / Kahn's algorithm)
        if not errors:
            cycle_error = cls._detect_cycles(step_keys, dependencies)
            if cycle_error:
                errors.append(cycle_error)

        return errors

    @classmethod
    def _detect_cycles(
        cls,
        step_keys: Set[str],
        dependencies: List[WorkflowDependencySchema],
    ) -> Optional[str]:
        """
        Detects circular dependencies in the workflow graph using Kahn's algorithm.
        Returns error string if cycle is found, or None if acyclic.
        """
        in_degree: Dict[str, int] = {k: 0 for k in step_keys}
        adjacency: Dict[str, List[str]] = {k: [] for k in step_keys}

        for dep in dependencies:
            src = dep.source_step_key
            tgt = dep.target_step_key
            if src in adjacency and tgt in in_degree:
                adjacency[src].append(tgt)
                in_degree[tgt] += 1

        # Queue of nodes with zero in-degree
        queue = [k for k, deg in in_degree.items() if deg == 0]
        visited_count = 0

        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for neighbor in adjacency.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(step_keys):
            unresolved = [k for k, deg in in_degree.items() if deg > 0]
            return f"Circular dependency cycle detected involving steps: {unresolved}"

        return None

    @classmethod
    def resolve_execution_order(
        cls,
        steps: List[WorkflowStepSchema],
        dependencies: List[WorkflowDependencySchema],
    ) -> List[str]:
        """
        Computes a valid topological execution order for the workflow DAG.
        Assumes graph has already been verified to be acyclic.
        """
        step_map = {s.step_key: s for s in steps}
        in_degree: Dict[str, int] = {k: 0 for k in step_map}
        adjacency: Dict[str, List[str]] = {k: [] for k in step_map}

        for dep in dependencies:
            adjacency[dep.source_step_key].append(dep.target_step_key)
            in_degree[dep.target_step_key] += 1

        # Sort queue by order_index for deterministic tie-breaking
        queue = sorted([k for k, deg in in_degree.items() if deg == 0], key=lambda k: step_map[k].order_index)
        execution_order: List[str] = []

        while queue:
            curr = queue.pop(0)
            execution_order.append(curr)
            for neighbor in sorted(adjacency[curr], key=lambda k: step_map[k].order_index):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return execution_order
