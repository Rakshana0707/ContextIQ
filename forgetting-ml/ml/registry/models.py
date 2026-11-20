"""
models.py

Data structures, exceptions, and transition validation logic for the ContextIQ Model Registry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from ml.registry.enums import ModelFamily, ModelLifecycleState, TaskType


class ModelRegistryError(Exception):
    """Base exception for all model registry errors."""
    pass


class InvalidStateTransitionError(ModelRegistryError):
    """Raised when an illegal lifecycle transition is attempted."""
    pass


class ArtifactNotFoundError(ModelRegistryError):
    """Raised when a referenced model artifact file cannot be found."""
    pass


class ArtifactOverwriteError(ModelRegistryError):
    """Raised when an attempt is made to overwrite an existing immutable model version."""
    pass


class ChecksumMismatchError(ModelRegistryError):
    """Raised when a model artifact's SHA-256 checksum does not match its registry record."""
    pass


class SchemaMismatchError(ModelRegistryError):
    """Raised when model feature schema does not match required feature specifications."""
    pass


# Strict lifecycle transition matrix
ALLOWED_TRANSITIONS: Dict[ModelLifecycleState, Set[ModelLifecycleState]] = {
    ModelLifecycleState.DEVELOPMENT: {
        ModelLifecycleState.TRAINING,
        ModelLifecycleState.REJECTED,
    },
    ModelLifecycleState.TRAINING: {
        ModelLifecycleState.VALIDATION,
        ModelLifecycleState.REJECTED,
    },
    ModelLifecycleState.VALIDATION: {
        ModelLifecycleState.CANDIDATE,
        ModelLifecycleState.REJECTED,
    },
    ModelLifecycleState.CANDIDATE: {
        ModelLifecycleState.APPROVED,
        ModelLifecycleState.REJECTED,
    },
    ModelLifecycleState.APPROVED: {
        ModelLifecycleState.PRODUCTION,
        ModelLifecycleState.ARCHIVED,
        ModelLifecycleState.REJECTED,
    },
    ModelLifecycleState.PRODUCTION: {
        ModelLifecycleState.ARCHIVED,
        ModelLifecycleState.REJECTED,
    },
    ModelLifecycleState.ARCHIVED: {
        ModelLifecycleState.PRODUCTION,  # Allowed during rollback
        ModelLifecycleState.REJECTED,
    },
    ModelLifecycleState.REJECTED: set(),  # Terminal state
}


@dataclass
class ModelMetadata:
    """Complete metadata record tracking a registered model."""
    model_id: str
    model_name: str
    model_version: str
    model_family: ModelFamily
    task_type: TaskType

    training_dataset_version: str
    feature_schema_version: str
    target_definition_version: str

    training_timestamp: str
    registered_at: str

    artifact_location: str
    artifact_checksum: str

    lifecycle_state: ModelLifecycleState = ModelLifecycleState.DEVELOPMENT
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    evaluation_metrics: Dict[str, Any] = field(default_factory=dict)
    calibration_config: Dict[str, Any] = field(default_factory=dict)
    shap_compatibility: Dict[str, Any] = field(default_factory=dict)

    feature_names_raw: List[str] = field(default_factory=list)
    feature_names_transformed: List[str] = field(default_factory=list)

    description: Optional[str] = None
    experiment_id: Optional[str] = None
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None

    def can_transition_to(self, new_state: ModelLifecycleState) -> bool:
        """Determines whether transition from current state to new_state is legal."""
        if self.lifecycle_state == new_state:
            return True
        allowed = ALLOWED_TRANSITIONS.get(self.lifecycle_state, set())
        return new_state in allowed

    def transition_to(
        self,
        new_state: ModelLifecycleState,
        actor: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Applies a lifecycle transition, raising InvalidStateTransitionError if illegal."""
        if not self.can_transition_to(new_state):
            raise InvalidStateTransitionError(
                f"Cannot transition model {self.model_id} from {self.lifecycle_state.value} "
                f"to {new_state.value}. Allowed transitions: "
                f"{[s.value for s in ALLOWED_TRANSITIONS.get(self.lifecycle_state, set())]}"
            )
        self.lifecycle_state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if new_state == ModelLifecycleState.APPROVED:
            self.approved_by = actor or "Lead Data Scientist"
            self.approval_notes = notes

    def to_dict(self) -> Dict[str, Any]:
        """Serializes metadata to a plain JSON-compatible dictionary."""
        d = asdict(self)
        d["model_family"] = self.model_family.value if hasattr(self.model_family, "value") else str(self.model_family)
        d["task_type"] = self.task_type.value if hasattr(self.task_type, "value") else str(self.task_type)
        d["lifecycle_state"] = self.lifecycle_state.value if hasattr(self.lifecycle_state, "value") else str(self.lifecycle_state)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        """Deserializes metadata from a dictionary."""
        d = dict(data)
        d["model_family"] = ModelFamily(d["model_family"])
        d["task_type"] = TaskType(d["task_type"])
        d["lifecycle_state"] = ModelLifecycleState(d["lifecycle_state"])
        return cls(**d)
