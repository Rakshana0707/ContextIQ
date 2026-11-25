"""
Import every ORM model here so that `Base.metadata` is fully populated
whenever `app.models` is imported -- this is required for
`Base.metadata.create_all()` (dev/test bootstrapping) and for any future
Alembic `env.py` to autogenerate correctly.
"""
from app.models.user import User  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.task_event import TaskEvent  # noqa: F401
from app.models.interruption import Interruption  # noqa: F401
from app.models.context_session import ContextSession  # noqa: F401
from app.models.task_association import TaskAssociation  # noqa: F401
from app.models.prediction import Prediction  # noqa: F401
from app.models.recommendation import Recommendation  # noqa: F401
from app.models.recommendation_feedback import RecommendationFeedback  # noqa: F401
from app.models.behaviour_metric import BehaviourMetric  # noqa: F401
from app.models.telemetry_consent import TelemetryConsent, UserPrivacySettings, UserAppExclusion  # noqa: F401
from app.models.raw_telemetry_event import RawTelemetryEvent  # noqa: F401
from app.models.detected_interruption import DetectedInterruption, DetectedInterruptionFeedback  # noqa: F401
from app.models.behavioral_profile import (  # noqa: F401
    UserBehavioralProfile,
    ProfileSnapshot,
    ProfileAuditLog,
)
from app.models.focus_window import UserFocusWindow  # noqa: F401
from app.models.task_ranking_feedback import TaskRankingFeedback  # noqa: F401
from app.models.user_intervention import UserIntervention  # noqa: F401
from app.models.bandit_models import BanditArmState, BanditDecisionLog, BanditRewardLog  # noqa: F401
from app.models.effectiveness_models import InterventionOutcome, InterventionExperiment  # noqa: F401
from app.models.notification_models import (  # noqa: F401
    UserNotification,
    UserNotificationPreference,
    NotificationFatigueRecord,
)
from app.models.calendar_integration import (  # noqa: F401
    CalendarIntegration,
    CalendarCredential,
    CalendarSyncState,
)
from app.models.external_calendar_event import ExternalCalendarEvent  # noqa: F401
from app.models.schedule_proposal import ScheduleProposal  # noqa: F401
from app.models.user_device import UserDevice  # noqa: F401
from app.models.location_checkin import LocationCheckIn  # noqa: F401
from app.models.location_routine_association import LocationRoutineAssociation  # noqa: F401
from app.models.simulation_models import SavedScenario, ProposedWorkflow  # noqa: F401
from app.models.automation_rule import (  # noqa: F401
    AutomationRule,
    AutomationTrigger,
    AutomationCondition,
    AutomationActionDefinition,
    AutomationExecution,
    AutomationRuleVersion,
)
from app.models.event_models import (
    StandardEventRecord,
    DeadLetterEventRecord,
    ProactiveFeedItem,
)
from app.models.workflow_models import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowDependency,
    WorkflowExecutionPlan,
    WorkflowStepExecution,
    WorkflowPlanVersion,
)
from app.models.policy_models import (
    UserPolicyConsent,
    PolicyAuditTrail,
)
from app.models.safety_models import (
    WorkflowAuditEvent,
    WorkflowApprovalRecord,
    WorkflowRollbackRecord,
    EmergencyStopEvent,
)

from app.models.enums import RecoveryState  # noqa: F401

__all__ = [
    "RecoveryState",

    "User",
    "Location",
    "Task",
    "TaskEvent",
    "Interruption",
    "ContextSession",
    "TaskAssociation",
    "Prediction",
    "Recommendation",
    "RecommendationFeedback",
    "BehaviourMetric",
    "TelemetryConsent",
    "UserPrivacySettings",
    "UserAppExclusion",
    "RawTelemetryEvent",
    "DetectedInterruption",
    "DetectedInterruptionFeedback",
    "UserBehavioralProfile",
    "ProfileSnapshot",
    "ProfileAuditLog",
    "UserFocusWindow",
    "TaskRankingFeedback",
    "UserIntervention",
    "BanditArmState",
    "BanditDecisionLog",
    "BanditRewardLog",
    "InterventionOutcome",
    "InterventionExperiment",
    "UserNotification",
    "UserNotificationPreference",
    "NotificationFatigueRecord",
    "CalendarIntegration",
    "CalendarCredential",
    "CalendarSyncState",
    "ExternalCalendarEvent",
    "ScheduleProposal",
    "UserDevice",
    "LocationCheckIn",
    "LocationRoutineAssociation",
    "SavedScenario",
    "ProposedWorkflow",
    "AutomationRule",
    "AutomationTrigger",
    "AutomationCondition",
    "AutomationActionDefinition",
    "AutomationExecution",
    "AutomationRuleVersion",
    "StandardEventRecord",
    "DeadLetterEventRecord",
    "ProactiveFeedItem",
    "WorkflowDefinition",
    "WorkflowStep",
    "WorkflowDependency",
    "WorkflowExecutionPlan",
    "WorkflowStepExecution",
    "WorkflowPlanVersion",
    "UserPolicyConsent",
    "PolicyAuditTrail",
    "WorkflowAuditEvent",
    "WorkflowApprovalRecord",
    "WorkflowRollbackRecord",
    "EmergencyStopEvent",
]


