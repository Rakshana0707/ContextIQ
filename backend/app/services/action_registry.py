"""
Action Registry for ContextIQ Autonomous Workflows (Phase 7.4).
Provides immutable definitions, permission requirements, risk tiers,
reversibility rules, and schema validators for all registered action contracts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.schemas.workflow_schemas import ActionContractSchema, WorkflowCategory


REGISTERED_ACTIONS: Dict[str, ActionContractSchema] = {
    # 1. Task Management
    "task:decompose_into_subtasks": ActionContractSchema(
        identifier="task:decompose_into_subtasks",
        category=WorkflowCategory.TASK_MANAGEMENT,
        description="Decomposes a complex parent task into smaller sequenced subtasks with discrete checkpoints.",
        required_permissions=["tasks:write"],
        risk_tier="Tier 1",
        is_reversible=True,
        compensating_action_identifier="task:batch_delete_subtasks",
        input_schema={
            "required": ["parent_task_id", "subtask_titles"],
            "types": {"parent_task_id": "string", "subtask_titles": "list"},
        },
        expected_output_schema={"created_subtask_ids": "list", "count": "int"},
        side_effects_description="Inserts child tasks into database linked to parent_task_id.",
    ),
    "task:update_priority": ActionContractSchema(
        identifier="task:update_priority",
        category=WorkflowCategory.TASK_MANAGEMENT,
        description="Updates the priority tier of an existing task to optimize focus sequence.",
        required_permissions=["tasks:write"],
        risk_tier="Tier 1",
        is_reversible=True,
        compensating_action_identifier="task:update_priority",
        input_schema={
            "required": ["task_id", "new_priority"],
            "types": {"task_id": "string", "new_priority": "string"},
            "allowed_priorities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        },
        expected_output_schema={"task_id": "string", "old_priority": "string", "new_priority": "string"},
        side_effects_description="Mutates priority column of task record in database.",
    ),
    "task:defer_task": ActionContractSchema(
        identifier="task:defer_task",
        category=WorkflowCategory.TASK_MANAGEMENT,
        description="Defers an interrupted or low-urgency task to a future execution window.",
        required_permissions=["tasks:write"],
        risk_tier="Tier 1",
        is_reversible=True,
        compensating_action_identifier="task:resume_task",
        input_schema={
            "required": ["task_id", "defer_until"],
            "types": {"task_id": "string", "defer_until": "string"},
        },
        expected_output_schema={"task_id": "string", "deferred_until": "string"},
        side_effects_description="Updates task scheduled state to DEFERRED.",
    ),

    # 2. Calendar Actions
    "calendar:insert_focus_block": ActionContractSchema(
        identifier="calendar:insert_focus_block",
        category=WorkflowCategory.CALENDAR,
        description="Creates a dedicated focus work block on the user's primary external calendar.",
        required_permissions=["calendar:write"],
        risk_tier="Tier 2",
        is_reversible=True,
        compensating_action_identifier="calendar:delete_event",
        input_schema={
            "required": ["title", "start_time", "end_time"],
            "types": {"title": "string", "start_time": "string", "end_time": "string"},
        },
        expected_output_schema={"external_event_id": "string", "scheduled_start": "string", "scheduled_end": "string"},
        side_effects_description="Creates remote calendar event on Google Calendar or MS Outlook.",
    ),
    "calendar:reschedule_event": ActionContractSchema(
        identifier="calendar:reschedule_event",
        category=WorkflowCategory.CALENDAR,
        description="Moves an existing calendar event or focus block to a circadian-optimized time slot.",
        required_permissions=["calendar:write"],
        risk_tier="Tier 2",
        is_reversible=True,
        compensating_action_identifier="calendar:reschedule_event",
        input_schema={
            "required": ["external_event_id", "new_start_time", "new_end_time"],
            "types": {"external_event_id": "string", "new_start_time": "string", "new_end_time": "string"},
        },
        expected_output_schema={"external_event_id": "string", "updated_start": "string", "updated_end": "string"},
        side_effects_description="Mutates remote calendar event start/end times.",
    ),

    # 3. Reminder & Nudge Actions
    "reminder:stage_context_warming": ActionContractSchema(
        identifier="reminder:stage_context_warming",
        category=WorkflowCategory.REMINDER,
        description="Pre-stages application context and schedules a gentle reminder 15m prior to deep work.",
        required_permissions=["notifications:write"],
        risk_tier="Tier 1",
        is_reversible=True,
        compensating_action_identifier="reminder:cancel_scheduled_notification",
        input_schema={
            "required": ["task_id", "lead_time_minutes"],
            "types": {"task_id": "string", "lead_time_minutes": "int"},
        },
        expected_output_schema={"reminder_id": "string", "scheduled_delivery_at": "string"},
        side_effects_description="Schedules a contextual notification in the user notification delivery queue.",
    ),
    "reminder:snooze_non_urgent": ActionContractSchema(
        identifier="reminder:snooze_non_urgent",
        category=WorkflowCategory.REMINDER,
        description="Throttles non-urgent desktop and push alerts during intense cognitive work periods.",
        required_permissions=["notifications:write"],
        risk_tier="Tier 1",
        is_reversible=True,
        compensating_action_identifier="reminder:restore_notification_delivery",
        input_schema={
            "required": ["throttle_duration_minutes"],
            "types": {"throttle_duration_minutes": "int"},
        },
        expected_output_schema={"throttled_until": "string"},
        side_effects_description="Sets delivery policy mute window for non-critical alerts.",
    ),

    # 4. Focus Session Actions
    "focus:create_session_block": ActionContractSchema(
        identifier="focus:create_session_block",
        category=WorkflowCategory.FOCUS_SESSION,
        description="Allocates an uninterruptible cognitive focus session with distraction shielding.",
        required_permissions=["focus:write", "desktop_agent:command"],
        risk_tier="Tier 2",
        is_reversible=True,
        compensating_action_identifier="focus:end_session_early",
        input_schema={
            "required": ["session_duration_minutes"],
            "types": {"session_duration_minutes": "int"},
        },
        expected_output_schema={"focus_session_id": "string", "duration_minutes": "int"},
        side_effects_description="Creates focus context session and activates desktop distraction shielding.",
    ),
    "focus:clamp_complementary_tools": ActionContractSchema(
        identifier="focus:clamp_complementary_tools",
        category=WorkflowCategory.FOCUS_SESSION,
        description="Pins primary IDE/work tools and minimizes distraction applications on workstation.",
        required_permissions=["desktop_agent:command"],
        risk_tier="Tier 1",
        is_reversible=True,
        compensating_action_identifier="focus:unclamp_tools",
        input_schema={
            "required": ["allowed_application_names"],
            "types": {"allowed_application_names": "list"},
        },
        expected_output_schema={"clamped_apps": "list", "minimized_count": "int"},
        side_effects_description="Dispatches window management command to local desktop agent.",
    ),

    # 5. Recovery Buffer Actions
    "recovery:insert_post_interruption_buffer": ActionContractSchema(
        identifier="recovery:insert_post_interruption_buffer",
        category=WorkflowCategory.RECOVERY_BUFFER,
        description="Inserts a cognitive cooldown recovery buffer following a disruptive interruption.",
        required_permissions=["calendar:write", "tasks:write"],
        risk_tier="Tier 2",
        is_reversible=True,
        compensating_action_identifier="calendar:delete_event",
        input_schema={
            "required": ["buffer_duration_minutes"],
            "types": {"buffer_duration_minutes": "int"},
        },
        expected_output_schema={"buffer_start": "string", "buffer_end": "string"},
        side_effects_description="Creates a recovery hold buffer on calendar and delays next task reminder.",
    ),
    "recovery:meeting_decompression_slot": ActionContractSchema(
        identifier="recovery:meeting_decompression_slot",
        category=WorkflowCategory.RECOVERY_BUFFER,
        description="Inserts a 10-minute breathing slot between consecutive dense calendar meetings.",
        required_permissions=["calendar:write"],
        risk_tier="Tier 2",
        is_reversible=True,
        compensating_action_identifier="calendar:delete_event",
        input_schema={
            "required": ["first_meeting_end", "second_meeting_start"],
            "types": {"first_meeting_end": "string", "second_meeting_start": "string"},
        },
        expected_output_schema={"slot_event_id": "string", "duration_minutes": "int"},
        side_effects_description="Inserts a 10m cognitive decompression hold between back-to-back meetings.",
    ),

    # 6. Behavioral Interventions
    "intervention:trigger_micro_break": ActionContractSchema(
        identifier="intervention:trigger_micro_break",
        category=WorkflowCategory.BEHAVIORAL_INTERVENTION,
        description="Deploys a targeted micro-break nudge when cognitive fatigue exceeds safe recovery thresholds.",
        required_permissions=["interventions:execute"],
        risk_tier="Tier 1",
        is_reversible=False,
        compensating_action_identifier=None,
        input_schema={
            "required": ["break_type", "duration_minutes"],
            "types": {"break_type": "string", "duration_minutes": "int"},
        },
        expected_output_schema={"nudge_id": "string", "delivered_at": "string"},
        side_effects_description="Dispatches immediate non-blocking break suggestion modal.",
    ),

    # 7. Cross-Device Synchronization
    "sync:cross_device_handoff": ActionContractSchema(
        identifier="sync:cross_device_handoff",
        category=WorkflowCategory.CROSS_DEVICE,
        description="Synchronizes active working memory context and open tasks across desktop and mobile devices.",
        required_permissions=["devices:sync"],
        risk_tier="Tier 1",
        is_reversible=True,
        compensating_action_identifier=None,
        input_schema={
            "required": ["target_device_id", "context_payload"],
            "types": {"target_device_id": "string", "context_payload": "dict"},
        },
        expected_output_schema={"sync_receipt_id": "string", "delivered_timestamp": "string"},
        side_effects_description="Sends synchronized context state to mobile companion or secondary workstation.",
    ),
}


class ActionRegistry:
    """Read-only registry catalog for querying and validating action contracts."""

    @classmethod
    def get(cls, action_identifier: str) -> Optional[ActionContractSchema]:
        return REGISTERED_ACTIONS.get(action_identifier)

    @classmethod
    def list_actions(cls, category: Optional[WorkflowCategory] = None) -> List[ActionContractSchema]:
        if category:
            return [a for a in REGISTERED_ACTIONS.values() if a.category == category]
        return list(REGISTERED_ACTIONS.values())

    @classmethod
    def is_registered(cls, action_identifier: str) -> bool:
        return action_identifier in REGISTERED_ACTIONS

    @classmethod
    def validate_action_parameters(cls, action_identifier: str, parameters: Dict[str, Any]) -> List[str]:
        """Validates that parameters satisfy registered input schema requirements."""
        action = cls.get(action_identifier)
        if not action:
            return [f"Unregistered action identifier: '{action_identifier}'"]

        errors: List[str] = []
        schema = action.input_schema
        required_fields = schema.get("required", [])

        for field in required_fields:
            if field not in parameters:
                errors.append(f"Missing required parameter '{field}' for action '{action_identifier}'")

        allowed_priorities = schema.get("allowed_priorities")
        if allowed_priorities and "new_priority" in parameters:
            val = str(parameters["new_priority"]).upper()
            if val not in allowed_priorities:
                errors.append(f"Invalid priority '{val}'. Must be one of {allowed_priorities}")

        return errors
