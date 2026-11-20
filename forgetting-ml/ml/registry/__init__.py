"""
ContextIQ Model Registry Package (Phase 2.9)
"""

from ml.registry.enums import ModelFamily, ModelLifecycleState, TaskType
from ml.registry.models import (
    ModelMetadata,
    ModelRegistryError,
    InvalidStateTransitionError,
    ArtifactNotFoundError,
    ArtifactOverwriteError,
    ChecksumMismatchError,
    SchemaMismatchError,
)
from ml.registry.artifact_store import ArtifactStore, compute_file_sha256
from ml.registry.registry import ModelRegistry
from ml.registry.auth import verify_admin_access

__all__ = [
    "ModelFamily",
    "ModelLifecycleState",
    "TaskType",
    "ModelMetadata",
    "ModelRegistryError",
    "InvalidStateTransitionError",
    "ArtifactNotFoundError",
    "ArtifactOverwriteError",
    "ChecksumMismatchError",
    "SchemaMismatchError",
    "ArtifactStore",
    "compute_file_sha256",
    "ModelRegistry",
    "verify_admin_access",
]
