"""
Standardized Intervention Taxonomy & Catalog (Phase 4.5).
Defines the 15 standardized intervention types, their categories, default efforts,
validity durations, and mutual contradiction matrix.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from app.schemas.intervention_schemas import EstimatedEffort, InterventionCategory, InterventionType


# Metadata definition for each intervention type
INTERVENTION_METADATA: Dict[str, Dict[str, Any]] = {
    # -----------------------------------------------------------------------
    # A. Focus Interventions
    # -----------------------------------------------------------------------
    InterventionType.SUGGEST_PROTECTED_FOCUS_SESSION.value: {
        "category": InterventionCategory.FOCUS.value,
        "title_template": "Protected Focus Block Recommended",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 2,
        "base_relevance": 78.0,
        "expected_outcome": "Shields upcoming cognitive work from notification fragmentation and micro-delays.",
    },
    InterventionType.REDUCE_APPLICATION_SWITCHING.value: {
        "category": InterventionCategory.FOCUS.value,
        "title_template": "Elevated Desktop Thrashing Detected",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 2,
        "base_relevance": 72.0,
        "expected_outcome": "Minimizes window switching overhead and preserves prospective working memory.",
    },
    InterventionType.SELECT_SUITABLE_FOCUS_WINDOW.value: {
        "category": InterventionCategory.FOCUS.value,
        "title_template": "Schedule for Peak Focus Window",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 8,
        "base_relevance": 70.0,
        "expected_outcome": "Aligns complex task execution with verified historical cognitive throughput.",
    },

    # -----------------------------------------------------------------------
    # B. Recovery Interventions
    # -----------------------------------------------------------------------
    InterventionType.SUGGEST_RECOVERY_BUFFER.value: {
        "category": InterventionCategory.RECOVERY.value,
        "title_template": "Elevated Behavioral Friction — Recovery Buffer Suggested",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 1,
        "base_relevance": 82.0,
        "expected_outcome": "Allows cognitive recovery to break disruption clusters and reset resumption latency.",
    },
    InterventionType.RESUME_PREVIOUS_TASK.value: {
        "category": InterventionCategory.RECOVERY.value,
        "title_template": "Resume Interrupted Task",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 2,
        "base_relevance": 76.0,
        "expected_outcome": "Recovers in-flight task continuity before working context decay exceeds critical threshold.",
    },
    InterventionType.REVIEW_LAST_COMPLETED_STEP.value: {
        "category": InterventionCategory.RECOVERY.value,
        "title_template": "Review Previous Task Step Before Resuming",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 2,
        "base_relevance": 68.0,
        "expected_outcome": "Re-establishes mental orientation after prolonged recovery micro-delay.",
    },

    # -----------------------------------------------------------------------
    # C. Task Interventions
    # -----------------------------------------------------------------------
    InterventionType.BREAK_LARGE_TASK.value: {
        "category": InterventionCategory.TASK.value,
        "title_template": "Decompose Long Task into Sub-Steps",
        "default_effort": EstimatedEffort.MEDIUM.value,
        "valid_duration_hours": 12,
        "base_relevance": 74.0,
        "expected_outcome": "Prevents cognitive fatigue and facilitates completion within typical focus sessions.",
    },
    InterventionType.REVIEW_APPROACHING_DEADLINE.value: {
        "category": InterventionCategory.TASK.value,
        "title_template": "Critical Deadline Approaching",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 4,
        "base_relevance": 88.0,
        "expected_outcome": "Ensures near-term completion before deadline expiration.",
    },
    InterventionType.POSTPONE_LOW_PRIORITY_TASK.value: {
        "category": InterventionCategory.TASK.value,
        "title_template": "Postpone Competing Low-Priority Work",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 6,
        "base_relevance": 65.0,
        "expected_outcome": "Frees cognitive bandwidth during high-friction or deadline-constrained sessions.",
    },

    # -----------------------------------------------------------------------
    # D. Contextual Interventions
    # -----------------------------------------------------------------------
    InterventionType.COMPLETE_ASSOCIATED_TASKS_LOCATION_EXIT.value: {
        "category": InterventionCategory.CONTEXTUAL.value,
        "title_template": "One More Thing Before Leaving",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 1,
        "base_relevance": 80.0,
        "expected_outcome": "Eliminates forgetfulness caused by physical location transition boundaries.",
    },
    InterventionType.PREPARE_SESSION_MATERIALS.value: {
        "category": InterventionCategory.CONTEXTUAL.value,
        "title_template": "Prepare Materials Ahead of Focus Session",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 3,
        "base_relevance": 66.0,
        "expected_outcome": "Removes setup latency so the user enters deep work with zero initial micro-delays.",
    },
    InterventionType.BATCH_RELATED_TASKS.value: {
        "category": InterventionCategory.CONTEXTUAL.value,
        "title_template": "Batch Related Tasks Together",
        "default_effort": EstimatedEffort.MEDIUM.value,
        "valid_duration_hours": 8,
        "base_relevance": 73.0,
        "expected_outcome": "Reduces context-switching overhead by clustering tasks in the same domain.",
    },

    # -----------------------------------------------------------------------
    # E. Workload Interventions
    # -----------------------------------------------------------------------
    InterventionType.REDISTRIBUTE_TASKS.value: {
        "category": InterventionCategory.WORKLOAD.value,
        "title_template": "Workload Exceeds Daily Focus Capacity",
        "default_effort": EstimatedEffort.HIGH.value,
        "valid_duration_hours": 12,
        "base_relevance": 75.0,
        "expected_outcome": "Prevents cognitive burnout by rebalancing overdue and pending commitments across upcoming days.",
    },
    InterventionType.REVIEW_COMPETING_DEADLINES.value: {
        "category": InterventionCategory.WORKLOAD.value,
        "title_template": "Clustered Deadlines Conflict",
        "default_effort": EstimatedEffort.MEDIUM.value,
        "valid_duration_hours": 6,
        "base_relevance": 82.0,
        "expected_outcome": "Resolves delivery conflicts between simultaneously due deliverables.",
    },
    InterventionType.REDUCE_EXCESSIVE_TASK_SWITCHING.value: {
        "category": InterventionCategory.WORKLOAD.value,
        "title_template": "Multiple Incomplete Tasks Started",
        "default_effort": EstimatedEffort.LOW.value,
        "valid_duration_hours": 3,
        "base_relevance": 77.0,
        "expected_outcome": "Stops task thrashing and channels attention into completing a single in-flight task.",
    },
}


# Mutually contradictory intervention pairs.
# If intervention A is selected, intervention B MUST NOT be presented in the same batch.
CONTRADICTION_PAIRS: List[Set[str]] = [
    # 1. Recovery break contradicts starting an immediate deep focus session
    {
        InterventionType.SUGGEST_RECOVERY_BUFFER.value,
        InterventionType.SUGGEST_PROTECTED_FOCUS_SESSION.value,
    },
    # 2. Postponing a task contradicts urgent deadline review for that task
    {
        InterventionType.POSTPONE_LOW_PRIORITY_TASK.value,
        InterventionType.REVIEW_APPROACHING_DEADLINE.value,
    },
    # 3. Switching reduction vs multi-task batching in high fragmentation
    {
        InterventionType.REDUCE_APPLICATION_SWITCHING.value,
        InterventionType.BATCH_RELATED_TASKS.value,
    },
]
