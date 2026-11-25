"""
Causal Directed Acyclic Graph (DAG) Registry & Target Trial Protocol Specifications (ContextIQ Phase 6.3).

Explicitly maps:
1. Assumed causal relationships between interventions and behavioral outcomes.
2. Backdoor confounding paths requiring adjustment.
3. Forbidden controls: Post-treatment mediators (which introduce over-controlling bias)
   and colliders (which induce M-bias / spurious associations).
4. Target trial specifications enforcing strict Time Zero (T0) alignment to eradicate immortal-time bias.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.schemas.causal_analysis import (
    CausalDAGDefinition,
    CausalEstimand,
    CausalQuestionId,
    DAGEdge,
    DAGNode,
    DAGNodeRole,
    TargetTrialProtocol,
)


# ===========================================================================
# 1. Target Trial Protocols
# ===========================================================================

TARGET_TRIAL_PROTOCOLS: Dict[CausalQuestionId, TargetTrialProtocol] = {
    CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION: TargetTrialProtocol(
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
        title="Target Trial 1: Scheduled Recovery Buffer vs Immediate Resumption on Task Return",
        eligibility_criteria=[
            "User experienced a detected cognitive interruption exceeding 60 seconds",
            "Disrupted task had an active in-progress status prior to interruption",
            "User has active telemetry consent and working session enabled",
            "Disrupted task deadline is not within the immediate 2 hours (safety exemption)",
        ],
        treatment_strategy="Deliver a scheduled cognitive recovery buffer (3-5 minutes) with context re-anchoring card at interruption termination.",
        control_strategy="Deliver no recovery buffer; allow immediate unassisted task resumption (standard practice).",
        time_zero_definition="Timestamp of cognitive interruption termination (t_T0). Treatment strategy is assigned strictly at t_T0.",
        follow_up_window="15 minutes following interruption termination [t_T0, t_T0 + 15 min].",
        outcome_definition="Confirmed task resumption (Y in {0, 1}) grounded in deliberate keyboard/IDE input within 15 minutes of T0.",
        causal_estimand=CausalEstimand.TREATMENT_EFFECT_ON_TREATED,
        analysis_plan="Doubly Robust AIPW and IPW estimation adjusting for pre-T0 confounders; sensitivity E-value evaluation.",
        immortal_time_bias_prevention=(
            "Eligibility is determined strictly prior to t_T0. Both treatment and control arms begin follow-up "
            "simultaneously at t_T0. Follow-up is never defined retroactively upon user returning to workstation."
        ),
    ),
    CausalQuestionId.ADAPTIVE_SCHEDULING_ON_COMPLETION: TargetTrialProtocol(
        question_id=CausalQuestionId.ADAPTIVE_SCHEDULING_ON_COMPLETION,
        title="Target Trial 2: Adaptive Calendar-Aware Scheduling vs Manual User Scheduling",
        eligibility_criteria=[
            "Task created with an explicit deadline between 4 hours and 7 days in advance",
            "User has authorized calendar integration (Google or Microsoft)",
            "User has logged at least 3 previous completed or abandoned tasks",
        ],
        treatment_strategy="Automatically block dedicated focus windows aligned with predicted circadian focus peaks.",
        control_strategy="Retain task in backlog without calendar modification; rely on manual user self-scheduling.",
        time_zero_definition="Timestamp of task creation and ingestion into ContextIQ (t_T0).",
        follow_up_window="From task creation t_T0 until explicit deadline expiration.",
        outcome_definition="Task completion (Y in {0, 1}) verified by completion event logged on or before scheduled deadline.",
        causal_estimand=CausalEstimand.AVERAGE_TREATMENT_EFFECT,
        analysis_plan="Propensity score matching and Doubly Robust AIPW with stratification by task complexity.",
        immortal_time_bias_prevention=(
            "Focus windows are assigned at task creation t_T0. Tasks that are deleted or modified within 5 minutes "
            "are excluded from both arms identically to prevent post-randomization selection bias."
        ),
    ),
    CausalQuestionId.PERSONALIZED_REMINDER_ON_ABANDONMENT: TargetTrialProtocol(
        question_id=CausalQuestionId.PERSONALIZED_REMINDER_ON_ABANDONMENT,
        title="Target Trial 3: Personalized Prospective Memory Nudge vs Passive Holdout",
        eligibility_criteria=[
            "Task is dormant (no progress logged for >= 48 hours)",
            "Predicted forgetting risk P_forget >= 0.40",
            "User has not received a reminder for this task within the preceding 24 hours",
        ],
        treatment_strategy="Deliver a personalized reminder notification optimized for current cognitive load.",
        control_strategy="Withhold notification (passive control holdout).",
        time_zero_definition="Moment when eligibility conditions and high forgetting risk are first verified (t_T0).",
        follow_up_window="72 hours following notification evaluation window [t_T0, t_T0 + 72 hours].",
        outcome_definition="Task abandonment or lapse (Y in {0, 1}), where Y=1 represents omission/abandonment and Y=0 represents task activity.",
        causal_estimand=CausalEstimand.AVERAGE_TREATMENT_EFFECT,
        analysis_plan="Inverse Probability Weighting with weight trimming; sensitivity analysis for unmeasured offline progress.",
        immortal_time_bias_prevention=(
            "Both treated and control cohorts are identified at the exact moment t_T0 when forgetting risk crosses threshold. "
            "Treatment delivery occurs within 60 seconds of t_T0."
        ),
    ),
    CausalQuestionId.NOTIFICATION_TIMING_ON_FRICTION: TargetTrialProtocol(
        question_id=CausalQuestionId.NOTIFICATION_TIMING_ON_FRICTION,
        title="Target Trial 4: Slack-Boundary Notification Timing vs Immediate In-Flow Interruption",
        eligibility_criteria=[
            "An actionable behavioral recommendation or calendar alert is enqueued for delivery",
            "User is currently active in a desktop session",
        ],
        treatment_strategy="Defer delivery until detected cognitive slack boundary (task transition or typing pause).",
        control_strategy="Deliver notification immediately regardless of ongoing keystroke/focus state.",
        time_zero_definition="Timestamp when notification payload is enqueued by intelligence service (t_T0).",
        follow_up_window="30 minutes following actual dispatch [t_dispatch, t_dispatch + 30 min].",
        outcome_definition="Continuous Behavioral Friction Index (BFI 0-100) measured across the subsequent 30-minute window.",
        causal_estimand=CausalEstimand.AVERAGE_TREATMENT_EFFECT,
        analysis_plan="G-computation Regression Adjustment and AIPW controlling for active cognitive load and meeting boundaries.",
        immortal_time_bias_prevention=(
            "Slack boundary waiting time is capped at a maximum of 120 seconds. Any alert not delivered by 120s is dispatched, "
            "and time-to-delivery is included as a continuous treatment variable to eliminate waiting-time immortal bias."
        ),
    ),
}


# ===========================================================================
# 2. Directed Acyclic Graph (DAG) Definitions
# ===========================================================================

def _build_recovery_buffer_dag() -> CausalDAGDefinition:
    nodes = [
        DAGNode(name="recovery_buffer", role=DAGNodeRole.TREATMENT, description="Scheduled cognitive recovery buffer delivery (0/1)", measurement_source="user_interventions"),
        DAGNode(name="task_resumption", role=DAGNodeRole.OUTCOME, description="Confirmed task resumption within 15 minutes (0/1)", measurement_source="detected_interruptions"),
        DAGNode(name="baseline_bfi", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Behavioral Friction Index in 60m preceding interruption", measurement_source="behaviour_metrics"),
        DAGNode(name="task_priority", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Priority level of disrupted task", measurement_source="tasks"),
        DAGNode(name="interruption_duration", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Duration of disruption in seconds", measurement_source="detected_interruptions"),
        DAGNode(name="hour_of_day", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Hour when interruption occurred (circadian peak/trough)", measurement_source="detected_interruptions"),
        DAGNode(name="calendar_meeting_density", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Number of scheduled meetings today", measurement_source="external_calendar_events"),
        DAGNode(name="context_card_read_latency", role=DAGNodeRole.POST_TREATMENT_MEDIATOR, description="Seconds spent reading recovery card - FORBIDDEN CONTROL", measurement_source="telemetry"),
        DAGNode(name="distraction_severity", role=DAGNodeRole.EFFECT_MODIFIER, description="Severity score of the interrupting event", measurement_source="detected_interruptions"),
        DAGNode(name="unmeasured_frustration", role=DAGNodeRole.UNMEASURED_CONFOUNDER, description="Unobserved emotional frustration and workplace stress", measurement_source="UNMEASURED"),
    ]
    edges = [
        DAGEdge(from_node="baseline_bfi", to_node="recovery_buffer", description="High friction triggers intervention recommendation"),
        DAGEdge(from_node="baseline_bfi", to_node="task_resumption", description="Fatigued users struggle to resume tasks"),
        DAGEdge(from_node="task_priority", to_node="recovery_buffer", description="Priority increases intervention probability"),
        DAGEdge(from_node="task_priority", to_node="task_resumption", description="Urgent tasks are resumed faster"),
        DAGEdge(from_node="interruption_duration", to_node="recovery_buffer", description="Long interruptions prompt recovery buffer"),
        DAGEdge(from_node="interruption_duration", to_node="task_resumption", description="Long interruptions degrade working memory context"),
        DAGEdge(from_node="calendar_meeting_density", to_node="recovery_buffer", description="Packed calendar influences buffer heuristics"),
        DAGEdge(from_node="calendar_meeting_density", to_node="task_resumption", description="Meeting proximity disrupts sustained focus"),
        DAGEdge(from_node="recovery_buffer", to_node="context_card_read_latency", description="Buffer delivery induces glance latency"),
        DAGEdge(from_node="context_card_read_latency", to_node="task_resumption", description="Card reading delays immediate resumption"),
        DAGEdge(from_node="recovery_buffer", to_node="task_resumption", description="Direct causal effect of cognitive re-anchoring"),
        DAGEdge(from_node="unmeasured_frustration", to_node="recovery_buffer", description="Frustrated behavior alters interaction patterns"),
        DAGEdge(from_node="unmeasured_frustration", to_node="task_resumption", description="Frustration inhibits cognitive recovery"),
    ]
    mermaid = (
        "graph TD\n"
        "    BFI[Baseline BFI] --> T[Recovery Buffer A]\n"
        "    BFI --> Y[Task Resumption Y]\n"
        "    PRIOR[Task Priority] --> T\n"
        "    PRIOR --> Y\n"
        "    DUR[Interruption Duration] --> T\n"
        "    DUR --> Y\n"
        "    CAL[Calendar Density] --> T\n"
        "    CAL --> Y\n"
        "    T -->|Causal Link| Y\n"
        "    T --> M[Context Card Read Latency (Mediator - Do Not Adjust)]\n"
        "    M --> Y\n"
        "    U((Unmeasured Frustration)) -.-> T\n"
        "    U -.-> Y"
    )
    return CausalDAGDefinition(
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
        title="DAG: Recovery Buffer on Confirmed Task Resumption",
        nodes=nodes,
        edges=edges,
        minimal_sufficient_adjustment_set=[
            "baseline_bfi",
            "task_priority",
            "interruption_duration",
            "hour_of_day",
            "calendar_meeting_density",
        ],
        forbidden_controls=["context_card_read_latency"],
        unmeasured_confounding_risks=[
            "Unmeasured cognitive fatigue or emotional frustration",
            "In-person coworker physical interruptions not captured in workstation telemetry",
        ],
        mermaid_diagram=mermaid,
    )


def _build_adaptive_scheduling_dag() -> CausalDAGDefinition:
    nodes = [
        DAGNode(name="adaptive_scheduling", role=DAGNodeRole.TREATMENT, description="Calendar-aware focus window scheduling (0/1)", measurement_source="schedule_proposals"),
        DAGNode(name="task_completion", role=DAGNodeRole.OUTCOME, description="Task completed before deadline (0/1)", measurement_source="tasks"),
        DAGNode(name="task_complexity", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Estimated complexity score of task", measurement_source="tasks"),
        DAGNode(name="historical_completion_rate", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="User 30-day task completion rate", measurement_source="tasks"),
        DAGNode(name="calendar_load", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Hours of scheduled meetings in the task window", measurement_source="external_calendar_events"),
        DAGNode(name="task_urgency", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Hours until deadline at task creation", measurement_source="tasks"),
        DAGNode(name="focus_window_duration", role=DAGNodeRole.POST_TREATMENT_MEDIATOR, description="Duration of scheduled focus window - FORBIDDEN CONTROL", measurement_source="focus_windows"),
        DAGNode(name="task_category", role=DAGNodeRole.EFFECT_MODIFIER, description="Category (Coding, DeepWork, Admin)", measurement_source="tasks"),
        DAGNode(name="unmeasured_external_commitments", role=DAGNodeRole.UNMEASURED_CONFOUNDER, description="Offline responsibilities not tracked on calendar", measurement_source="UNMEASURED"),
    ]
    edges = [
        DAGEdge(from_node="task_complexity", to_node="adaptive_scheduling", description="Complex tasks trigger auto-scheduling"),
        DAGEdge(from_node="task_complexity", to_node="task_completion", description="Complex tasks are harder to complete"),
        DAGEdge(from_node="calendar_load", to_node="adaptive_scheduling", description="High meeting load requires scheduling optimization"),
        DAGEdge(from_node="calendar_load", to_node="task_completion", description="Meeting load reduces available focus time"),
        DAGEdge(from_node="historical_completion_rate", to_node="task_completion", description="High past completion correlates with future completion"),
        DAGEdge(from_node="task_urgency", to_node="adaptive_scheduling", description="Urgency triggers immediate scheduling heuristics"),
        DAGEdge(from_node="adaptive_scheduling", to_node="focus_window_duration", description="Scheduling generates dedicated focus blocks"),
        DAGEdge(from_node="focus_window_duration", to_node="task_completion", description="Focus blocks provide time for completion"),
        DAGEdge(from_node="adaptive_scheduling", to_node="task_completion", description="Direct causal impact of proactive scheduling"),
        DAGEdge(from_node="unmeasured_external_commitments", to_node="adaptive_scheduling", description="Hidden workload affects user willingness to schedule"),
        DAGEdge(from_node="unmeasured_external_commitments", to_node="task_completion", description="Hidden workload preempts task completion"),
    ]
    mermaid = (
        "graph TD\n"
        "    COMP[Task Complexity] --> T[Adaptive Scheduling A]\n"
        "    COMP --> Y[Task Completion Y]\n"
        "    LOAD[Calendar Load] --> T\n"
        "    LOAD --> Y\n"
        "    URG[Task Urgency] --> T\n"
        "    URG --> Y\n"
        "    HIST[Historical Completion Rate] --> Y\n"
        "    T -->|Causal Link| Y\n"
        "    T --> M[Focus Window Duration (Mediator - Do Not Adjust)]\n"
        "    M --> Y\n"
        "    U((Unmeasured External Commitments)) -.-> T\n"
        "    U -.-> Y"
    )
    return CausalDAGDefinition(
        question_id=CausalQuestionId.ADAPTIVE_SCHEDULING_ON_COMPLETION,
        title="DAG: Adaptive Scheduling on Task Completion",
        nodes=nodes,
        edges=edges,
        minimal_sufficient_adjustment_set=[
            "task_complexity",
            "historical_completion_rate",
            "calendar_load",
            "task_urgency",
        ],
        forbidden_controls=["focus_window_duration"],
        unmeasured_confounding_risks=[
            "Offline workplace demands and family commitments not reflected in digital calendar",
            "Unreported task dependencies waiting on external team members",
        ],
        mermaid_diagram=mermaid,
    )


def _build_personalized_reminder_dag() -> CausalDAGDefinition:
    nodes = [
        DAGNode(name="personalized_reminder", role=DAGNodeRole.TREATMENT, description="Delivered reminder nudge (0/1)", measurement_source="notification_models"),
        DAGNode(name="task_abandonment", role=DAGNodeRole.OUTCOME, description="Task abandoned / forgotten without progress (0/1)", measurement_source="tasks"),
        DAGNode(name="task_age_hours", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Hours elapsed since task creation", measurement_source="tasks"),
        DAGNode(name="forgetting_risk_score", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Predicted forgetting risk at T0", measurement_source="predictions"),
        DAGNode(name="trailing_interruption_rate", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Recent interruptions per hour", measurement_source="detected_interruptions"),
        DAGNode(name="task_priority", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Priority classification of task", measurement_source="tasks"),
        DAGNode(name="notification_dismissal_speed", role=DAGNodeRole.POST_TREATMENT_MEDIATOR, description="Reaction time in dismissing alert - FORBIDDEN CONTROL", measurement_source="notification_feedback"),
        DAGNode(name="time_of_day", role=DAGNodeRole.EFFECT_MODIFIER, description="Morning vs afternoon delivery timing", measurement_source="notification_models"),
        DAGNode(name="unmeasured_offline_progress", role=DAGNodeRole.UNMEASURED_CONFOUNDER, description="Task progress conducted on paper or mobile offline", measurement_source="UNMEASURED"),
    ]
    edges = [
        DAGEdge(from_node="task_age_hours", to_node="personalized_reminder", description="Older tasks trigger reminder rules"),
        DAGEdge(from_node="task_age_hours", to_node="task_abandonment", description="Older tasks are more likely to be abandoned"),
        DAGEdge(from_node="forgetting_risk_score", to_node="personalized_reminder", description="High risk score causes intervention delivery"),
        DAGEdge(from_node="forgetting_risk_score", to_node="task_abandonment", description="High forgetting risk predicts abandonment"),
        DAGEdge(from_node="trailing_interruption_rate", to_node="personalized_reminder", description="High disruption shifts dispatch timing"),
        DAGEdge(from_node="trailing_interruption_rate", to_node="task_abandonment", description="Frequent disruption induces task omission"),
        DAGEdge(from_node="personalized_reminder", to_node="notification_dismissal_speed", description="Reminder creates opportunity for dismissal"),
        DAGEdge(from_node="notification_dismissal_speed", to_node="task_abandonment", description="Instant dismissal correlates with non-action"),
        DAGEdge(from_node="personalized_reminder", to_node="task_abandonment", description="Direct causal impact of cognitive alerting"),
        DAGEdge(from_node="unmeasured_offline_progress", to_node="personalized_reminder", description="User appears idle causing false alarm nudge"),
        DAGEdge(from_node="unmeasured_offline_progress", to_node="task_abandonment", description="User finishes offline so task is not abandoned"),
    ]
    mermaid = (
        "graph TD\n"
        "    AGE[Task Age Hours] --> T[Personalized Reminder A]\n"
        "    AGE --> Y[Task Abandonment Y]\n"
        "    RISK[Forgetting Risk Score] --> T\n"
        "    RISK --> Y\n"
        "    INT[Trailing Interruption Rate] --> T\n"
        "    INT --> Y\n"
        "    PRIOR[Task Priority] --> T\n"
        "    PRIOR --> Y\n"
        "    T -->|Causal Link| Y\n"
        "    T --> M[Notification Dismissal Speed (Mediator - Do Not Adjust)]\n"
        "    M --> Y\n"
        "    U((Unmeasured Offline Progress)) -.-> T\n"
        "    U -.-> Y"
    )
    return CausalDAGDefinition(
        question_id=CausalQuestionId.PERSONALIZED_REMINDER_ON_ABANDONMENT,
        title="DAG: Personalized Reminder on Task Abandonment",
        nodes=nodes,
        edges=edges,
        minimal_sufficient_adjustment_set=[
            "task_age_hours",
            "forgetting_risk_score",
            "trailing_interruption_rate",
            "task_priority",
        ],
        forbidden_controls=["notification_dismissal_speed"],
        unmeasured_confounding_risks=[
            "Offline progress made on external hardware, whiteboard, or paper",
            "User resolved the task orally without updating software system",
        ],
        mermaid_diagram=mermaid,
    )


def _build_notification_timing_dag() -> CausalDAGDefinition:
    nodes = [
        DAGNode(name="slack_timed_notification", role=DAGNodeRole.TREATMENT, description="Delivered at detected cognitive slack boundary (0/1)", measurement_source="notification_models"),
        DAGNode(name="subsequent_bfi", role=DAGNodeRole.OUTCOME, description="Behavioral Friction Index (0-100) in subsequent 30m", measurement_source="behaviour_metrics"),
        DAGNode(name="current_cognitive_load", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Focus depth and typing cadence at enqueue time", measurement_source="raw_telemetry_events"),
        DAGNode(name="typing_velocity", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Keystrokes per minute leading up to enqueue", measurement_source="raw_telemetry_events"),
        DAGNode(name="meeting_boundary_proximity", role=DAGNodeRole.PRE_TREATMENT_CONFOUNDER, description="Minutes until next calendar event", measurement_source="external_calendar_events"),
        DAGNode(name="immediate_app_switch", role=DAGNodeRole.POST_TREATMENT_MEDIATOR, description="Immediate switch away from current app - FORBIDDEN CONTROL", measurement_source="raw_telemetry_events"),
        DAGNode(name="context_switch_frequency", role=DAGNodeRole.EFFECT_MODIFIER, description="Baseline user switching rate", measurement_source="behaviour_metrics"),
        DAGNode(name="unmeasured_interpersonal_pressure", role=DAGNodeRole.UNMEASURED_CONFOUNDER, description="Urgent real-time workplace chat pressure", measurement_source="UNMEASURED"),
    ]
    edges = [
        DAGEdge(from_node="current_cognitive_load", to_node="slack_timed_notification", description="High load prompts postponement to slack boundary"),
        DAGEdge(from_node="current_cognitive_load", to_node="subsequent_bfi", description="Deep load resists interruption friction differently"),
        DAGEdge(from_node="typing_velocity", to_node="slack_timed_notification", description="Active typing delays notification dispatch"),
        DAGEdge(from_node="typing_velocity", to_node="subsequent_bfi", description="Active flow state disruption causes high friction spike"),
        DAGEdge(from_node="meeting_boundary_proximity", to_node="slack_timed_notification", description="Impending meeting forces early or batched alert"),
        DAGEdge(from_node="meeting_boundary_proximity", to_node="subsequent_bfi", description="Meeting rush elevates baseline friction"),
        DAGEdge(from_node="slack_timed_notification", to_node="immediate_app_switch", description="Timed delivery changes likelihood of sudden tab switch"),
        DAGEdge(from_node="immediate_app_switch", to_node="subsequent_bfi", description="App switch introduces immediate context loss"),
        DAGEdge(from_node="slack_timed_notification", to_node="subsequent_bfi", description="Direct causal reduction in distraction and friction"),
        DAGEdge(from_node="unmeasured_interpersonal_pressure", to_node="slack_timed_notification", description="Urgent coworker pings disrupt timing logic"),
        DAGEdge(from_node="unmeasured_interpersonal_pressure", to_node="subsequent_bfi", description="Pressure directly increases stress and friction"),
    ]
    mermaid = (
        "graph TD\n"
        "    LOAD[Current Cognitive Load] --> T[Slack-Timed Notification A]\n"
        "    LOAD --> Y[Subsequent BFI Y]\n"
        "    TYPE[Typing Velocity] --> T\n"
        "    TYPE --> Y\n"
        "    MEET[Meeting Boundary Proximity] --> T\n"
        "    MEET --> Y\n"
        "    T -->|Causal Link| Y\n"
        "    T --> M[Immediate App Switch (Mediator - Do Not Adjust)]\n"
        "    M --> Y\n"
        "    U((Unmeasured Workplace Pressure)) -.-> T\n"
        "    U -.-> Y"
    )
    return CausalDAGDefinition(
        question_id=CausalQuestionId.NOTIFICATION_TIMING_ON_FRICTION,
        title="DAG: Notification Timing on Subsequent Behavioral Friction",
        nodes=nodes,
        edges=edges,
        minimal_sufficient_adjustment_set=[
            "current_cognitive_load",
            "typing_velocity",
            "meeting_boundary_proximity",
        ],
        forbidden_controls=["immediate_app_switch"],
        unmeasured_confounding_risks=[
            "Unmeasured real-time workplace chat interruptions (Slack/Teams DMs)",
            "Urgent emotional distress not tracked in system events",
        ],
        mermaid_diagram=mermaid,
    )


CAUSAL_DAG_REGISTRY: Dict[CausalQuestionId, CausalDAGDefinition] = {
    CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION: _build_recovery_buffer_dag(),
    CausalQuestionId.ADAPTIVE_SCHEDULING_ON_COMPLETION: _build_adaptive_scheduling_dag(),
    CausalQuestionId.PERSONALIZED_REMINDER_ON_ABANDONMENT: _build_personalized_reminder_dag(),
    CausalQuestionId.NOTIFICATION_TIMING_ON_FRICTION: _build_notification_timing_dag(),
}


def get_causal_dag(question_id: CausalQuestionId) -> Optional[CausalDAGDefinition]:
    """Retrieves the authoritative DAG definition for a research question."""
    return CAUSAL_DAG_REGISTRY.get(question_id)


def get_target_trial(question_id: CausalQuestionId) -> Optional[TargetTrialProtocol]:
    """Retrieves the target trial protocol for a research question."""
    return TARGET_TRIAL_PROTOCOLS.get(question_id)


def list_all_causal_questions() -> List[Dict[str, Any]]:
    """Returns summaries of all 4 supported causal research questions."""
    return [
        {
            "question_id": q_id.value,
            "title": dag.title,
            "treatment_node": [n.name for n in dag.nodes if n.role == DAGNodeRole.TREATMENT][0],
            "outcome_node": [n.name for n in dag.nodes if n.role == DAGNodeRole.OUTCOME][0],
            "adjustment_set": dag.minimal_sufficient_adjustment_set,
            "forbidden_controls": dag.forbidden_controls,
            "unmeasured_risks_count": len(dag.unmeasured_confounding_risks),
        }
        for q_id, dag in CAUSAL_DAG_REGISTRY.items()
    ]
