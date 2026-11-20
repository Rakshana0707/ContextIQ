"""
artifact_store.py

Versioned, immutable artifact storage with SHA-256 checksum integrity verification
and schema compatibility enforcement for ContextIQ.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib

from ml.features.feature_spec import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from ml.registry.enums import TaskType
from ml.registry.models import (
    ArtifactNotFoundError,
    ArtifactOverwriteError,
    ChecksumMismatchError,
    SchemaMismatchError,
)

ROOT = Path(__file__).resolve().parents[2]


def compute_file_sha256(file_path: Union[str, Path]) -> str:
    """Computes hexadecimal SHA-256 digest of a file in streaming chunks."""
    path = Path(file_path)
    if not path.exists():
        raise ArtifactNotFoundError(f"Artifact file not found: {path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class ArtifactStore:
    """
    Manages physical storage of versioned ML artifacts:
    - Versioned, hierarchical directory layouts
    - Strict immutable artifact protection (no silent overwriting)
    - Cryptographic SHA-256 integrity validation
    - Feature schema compatibility checking
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else ROOT / "artifacts" / "models"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_version_dir(self, task_type: TaskType, model_name: str, version: str) -> Path:
        """Returns the canonical versioned directory path."""
        t_type = task_type.value if hasattr(task_type, "value") else str(task_type)
        return self.base_dir / t_type / model_name / f"v{version.lstrip('v')}"

    def save_artifact(
        self,
        bundle: Dict[str, Any],
        task_type: TaskType,
        model_name: str,
        version: str,
        overwrite: bool = False,
    ) -> Tuple[Path, str]:
        """
        Saves a model bundle into the versioned artifact directory.
        Returns (saved_path, sha256_checksum).
        """
        version_dir = self.get_version_dir(task_type, model_name, version)
        artifact_path = version_dir / "model_bundle.joblib"

        if artifact_path.exists() and not overwrite:
            raise ArtifactOverwriteError(
                f"Artifact already exists at {artifact_path}. "
                "Versioned artifacts are immutable and cannot be overwritten without overwrite=True."
            )

        version_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, artifact_path, compress=3)
        checksum = compute_file_sha256(artifact_path)
        return artifact_path, checksum

    def load_artifact(
        self,
        artifact_location: Union[str, Path],
        expected_checksum: Optional[str] = None,
        verify_schema: bool = True,
    ) -> Dict[str, Any]:
        """
        Loads and validates a model artifact:
        1. Checks existence
        2. Validates SHA-256 checksum against expected_checksum
        3. Validates feature schema structure
        """
        path = Path(artifact_location)
        if not path.is_absolute():
            path = ROOT / path

        if not path.exists():
            raise ArtifactNotFoundError(f"Model artifact not found at {path}")

        if expected_checksum:
            actual_checksum = compute_file_sha256(path)
            if actual_checksum != expected_checksum:
                raise ChecksumMismatchError(
                    f"Integrity check failed for {path}!\n"
                    f"Expected SHA-256: {expected_checksum}\n"
                    f"Actual SHA-256:   {actual_checksum}\n"
                    "Artifact may be corrupted or tampered with."
                )

        try:
            bundle = joblib.load(path)
        except Exception as e:
            raise ArtifactNotFoundError(f"Failed to deserialize model bundle at {path}: {str(e)}") from e

        if verify_schema and isinstance(bundle, dict):
            self.verify_feature_schema(bundle)

        return bundle

    def verify_feature_schema(self, bundle: Dict[str, Any]) -> bool:
        """
        Verifies that the bundle defines required feature lists matching the active schema.
        Applicable to tabular classification bundles.
        """
        if "categorical_features" not in bundle or "numeric_features" not in bundle:
            # Non-tabular models (or survival pipelines with internal feature handling)
            return True

        bundle_cats = set(bundle.get("categorical_features", []))
        bundle_nums = set(bundle.get("numeric_features", []))
        bundle_all = bundle_cats.union(bundle_nums)

        required_all = set(CATEGORICAL_FEATURES).union(set(NUMERIC_FEATURES))
        missing = required_all - bundle_all
        if missing:
            raise SchemaMismatchError(
                f"Model bundle missing expected features from active schema: {sorted(missing)}"
            )

        return True
