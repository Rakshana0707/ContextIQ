"""
Enumerations shared across the ContextIQ data model.

These are implemented as Python `str` Enums and mapped to native Postgres
ENUM types via SQLAlchemy's `Enum(..., native_enum=True)`. Keeping them in
one module prevents drift between ORM models, Pydantic schemas, and
Alembic-style migration SQL.
"""
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FORGOTTEN = "FORGOTTEN"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskEventType(str, Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    COMPLETED = "COMPLETED"
    FORGOTTEN = "FORGOTTEN"
    CANCELLED = "CANCELLED"


class InterruptionType(str, Enum):
    PHONE = "PHONE"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    MESSAGE = "MESSAGE"
    CALL = "CALL"
    SEARCH = "SEARCH"
    PERSON = "PERSON"
    FOOD = "FOOD"
    OTHER = "OTHER"


class LocationType(str, Enum):
    HOME = "HOME"
    WORK = "WORK"
    OFFICE = "OFFICE"
    CAMPUS = "CAMPUS"
    LIBRARY = "LIBRARY"
    LABORATORY = "LABORATORY"
    GYM = "GYM"
    COMMUTE = "COMMUTE"
    STUDY = "STUDY"
    OTHER = "OTHER"


class CheckInType(str, Enum):
    MANUAL = "MANUAL"
    GEOFENCE_ENTER = "GEOFENCE_ENTER"
    GEOFENCE_EXIT = "GEOFENCE_EXIT"


class RoutineAssociationSource(str, Enum):
    EXPLICIT = "EXPLICIT"
    STATISTICALLY_OBSERVED = "STATISTICALLY_OBSERVED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class AssociationType(str, Enum):
    OFTEN_FORGOTTEN_WITH = "OFTEN_FORGOTTEN_WITH"   # "one more thing" pattern
    SEQUENTIAL = "SEQUENTIAL"                        # task A usually precedes task B
    BLOCKS = "BLOCKS"                                 # task A blocks task B
    CONTEXT_LINKED = "CONTEXT_LINKED"                 # tasks share a context/location trigger


class PredictionType(str, Enum):
    FORGET_RISK = "FORGET_RISK"
    OPTIMAL_TIME_WINDOW = "OPTIMAL_TIME_WINDOW"
    CONTEXT_SWITCH_RISK = "CONTEXT_SWITCH_RISK"
    INTERRUPTION_RISK = "INTERRUPTION_RISK"
    ONE_MORE_THING = "ONE_MORE_THING"


class RecommendationType(str, Enum):
    REMINDER = "REMINDER"
    SCHEDULE_SHIFT = "SCHEDULE_SHIFT"
    BATCH_TASKS = "BATCH_TASKS"
    LOCATION_TRIGGER = "LOCATION_TRIGGER"
    BREAK_SUGGESTION = "BREAK_SUGGESTION"
    ONE_MORE_THING_NUDGE = "ONE_MORE_THING_NUDGE"


class RecommendationStatus(str, Enum):
    PENDING = "PENDING"
    SHOWN = "SHOWN"
    ACCEPTED = "ACCEPTED"
    DISMISSED = "DISMISSED"
    EXPIRED = "EXPIRED"


class RecommendationFeedbackAction(str, Enum):
    ACCEPTED = "ACCEPTED"
    DISMISSED = "DISMISSED"
    DEFERRED = "DEFERRED"


class BehaviourMetricType(str, Enum):
    FORGOTTEN_TASK_RATE = "FORGOTTEN_TASK_RATE"
    AVG_INTERRUPTIONS_PER_SESSION = "AVG_INTERRUPTIONS_PER_SESSION"
    CONTEXT_SWITCH_COUNT = "CONTEXT_SWITCH_COUNT"
    FOCUS_MINUTES = "FOCUS_MINUTES"
    TASK_COMPLETION_RATE = "TASK_COMPLETION_RATE"
    AVG_TASK_DELAY_MINUTES = "AVG_TASK_DELAY_MINUTES"


class ConsentStatus(str, Enum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"


class TelemetryCategory(str, Enum):
    APP_TRANSITIONS = "APP_TRANSITIONS"
    INACTIVITY_DETECTION = "INACTIVITY_DETECTION"
    SESSION_RECONSTRUCTION = "SESSION_RECONSTRUCTION"
    BEHAVIORAL_ANALYTICS = "BEHAVIORAL_ANALYTICS"
    LOCAL_STORAGE = "LOCAL_STORAGE"
    SERVER_SYNC = "SERVER_SYNC"


class TelemetryEventType(str, Enum):
    APPLICATION_ACTIVATED = "application_activated"
    APPLICATION_DEACTIVATED = "application_deactivated"
    USER_IDLE_STARTED = "user_idle_started"
    USER_ACTIVE_RETURNED = "user_active_returned"
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    TELEMETRY_PAUSED = "telemetry_paused"
    TELEMETRY_RESUMED = "telemetry_resumed"
    HEARTBEAT = "heartbeat"


class DetectedInterruptionType(str, Enum):
    APPLICATION_SWITCH = "APPLICATION_SWITCH"
    IDLE_INTERRUPTION = "IDLE_INTERRUPTION"
    SESSION_DISRUPTION = "SESSION_DISRUPTION"
    CONTEXT_SWITCH = "CONTEXT_SWITCH"
    UNKNOWN_INTERRUPTION = "UNKNOWN_INTERRUPTION"


class InterruptionSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class InterruptionFeedbackClassification(str, Enum):
    GENUINE_INTERRUPTION = "GENUINE_INTERRUPTION"
    INTENTIONAL_SWITCH = "INTENTIONAL_SWITCH"
    IGNORE = "IGNORE"
    INCORRECT_DETECTION = "INCORRECT_DETECTION"


class RecoveryState(str, Enum):
    INTERRUPTION_DETECTED = "INTERRUPTION_DETECTED"
    APP_OR_TASK_REVISITED = "APP_OR_TASK_REVISITED"
    ORIGINAL_CONTEXT_RESTORED = "ORIGINAL_CONTEXT_RESTORED"
    CONFIRMED_TASK_RESUMPTION = "CONFIRMED_TASK_RESUMPTION"
    TASK_COMPLETED = "TASK_COMPLETED"
    RECOVERY_NOT_OBSERVED = "RECOVERY_NOT_OBSERVED"


class GraphNodeType(str, Enum):
    """Supported node types in the unified ContextIQ Knowledge Graph (Phase 8.1)."""
    USER = "USER"
    TASK = "TASK"
    PROJECT = "PROJECT"
    GOAL = "GOAL"
    MILESTONE = "MILESTONE"
    HABIT = "HABIT"
    BEHAVIORAL_PATTERN = "BEHAVIORAL_PATTERN"
    CONTEXT = "CONTEXT"
    INTERRUPTION = "INTERRUPTION"
    RECOMMENDATION = "RECOMMENDATION"
    DECISION = "DECISION"
    CALENDAR_EVENT = "CALENDAR_EVENT"
    WORKFLOW = "WORKFLOW"
    OUTCOME = "OUTCOME"
    RESOURCE = "RESOURCE"


class GraphRelationshipType(str, Enum):
    """Directional relationship semantics linking entities across the Knowledge Graph."""
    BELONGS_TO = "BELONGS_TO"
    DEPENDS_ON = "DEPENDS_ON"
    CONTRIBUTES_TO = "CONTRIBUTES_TO"
    BLOCKS = "BLOCKS"
    RELATED_TO = "RELATED_TO"
    GENERATED_BY = "GENERATED_BY"
    INFLUENCES = "INFLUENCES"
    PRECEDED_BY = "PRECEDED_BY"
    RESULTED_IN = "RESULTED_IN"
    SUPPORTS = "SUPPORTS"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    COMPLETED_AS = "COMPLETED_AS"
    DERIVED_FROM = "DERIVED_FROM"


class KnowledgeEvidenceSource(str, Enum):
    """Formal provenance source of knowledge facts and relationships."""
    EXPLICIT_USER = "EXPLICIT_USER"
    APPLICATION_EVENT = "APPLICATION_EVENT"
    CALENDAR_IMPORT = "CALENDAR_IMPORT"
    STATISTICAL_ANALYSIS = "STATISTICAL_ANALYSIS"
    ML_PREDICTION = "ML_PREDICTION"
    LLM_HYPOTHESIS = "LLM_HYPOTHESIS"

