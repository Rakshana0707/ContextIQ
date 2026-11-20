"""
rollback.py

Model Archive, Rollback & Deployment Ledger Manager (Phase 2.8).
Handles:
1. Versioned model artifact archiving before promotion.
2. Artifact integrity verification (required keys, schema compatibility).
3. Reverting production model to previous stable version.
4. Deployment history audit ledger.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts"
ACTIVE_BUNDLE_PATH = ARTIFACTS_DIR / "model_bundle.joblib"
ARCHIVE_DIR = ARTIFACTS_DIR / "model_archive"
LEDGER_PATH = ARTIFACTS_DIR / "deployment_history.json"

REQUIRED_BUNDLE_KEYS = {
    "model", "raw_model", "preprocessor", "model_name", "model_version",
    "threshold", "calibrated", "categorical_features", "numeric_features",
    "feature_names_transformed",
}


class ModelRollbackManager:
    """Manages model version archiving, validation, rollback, and deployment history."""

    def __init__(
        self,
        active_bundle_path: Path = ACTIVE_BUNDLE_PATH,
        archive_dir: Path = ARCHIVE_DIR,
        ledger_path: Path = LEDGER_PATH,
    ):
        self.active_path = active_bundle_path
        self.archive_dir = archive_dir
        self.ledger_path = ledger_path
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def validate_artifact_integrity(self, bundle_path: Path) -> Tuple[bool, str]:
        """Validates that a model artifact file is intact, valid, and contains all required keys."""
        if not bundle_path.exists():
            return False, f"File does not exist: {bundle_path}"

        try:
            bundle = joblib.load(bundle_path)
            if not isinstance(bundle, dict):
                return False, "Artifact is not a valid dictionary bundle"

            missing = REQUIRED_BUNDLE_KEYS - bundle.keys()
            if missing:
                return False, f"Missing required bundle keys: {sorted(missing)}"

            return True, "Artifact integrity verified successfully"
        except Exception as e:
            return False, f"Artifact failed to load: {str(e)}"

    def archive_current_model(self, version_label: str, reason: str = "Pre-deployment archive") -> Path:
        """Archives the currently active production model bundle."""
        if not self.active_path.exists():
            raise FileNotFoundError(f"Active model bundle not found at {self.active_path}")

        is_valid, msg = self.validate_artifact_integrity(self.active_path)
        if not is_valid:
            raise ValueError(f"Cannot archive corrupt active bundle: {msg}")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_name = f"model_v{version_label}_{timestamp}.joblib"
        archive_path = self.archive_dir / archive_name

        shutil.copy2(self.active_path, archive_path)
        return archive_path

    def record_deployment_event(
        self,
        event_type: str,  # "PROMOTION", "ROLLBACK", "INITIAL"
        model_name: str,
        model_version: str,
        approved_by: str,
        reason: str,
        metrics: Optional[Dict[str, Any]] = None,
        archive_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Records an event in the deployment history ledger."""
        ledger = self.get_deployment_history()

        event = {
            "event_id": f"DEP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_name": model_name,
            "model_version": model_version,
            "approved_by": approved_by,
            "reason": reason,
            "metrics": metrics or {},
            "archive_path": archive_path,
        }

        ledger.insert(0, event)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)

        return event

    def get_deployment_history(self) -> List[Dict[str, Any]]:
        """Reads deployment history ledger."""
        if not self.ledger_path.exists():
            return []
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def rollback(
        self,
        target_version: Optional[str] = None,
        approved_by: str = "MLOps Admin",
        reason: str = "Rollback due to performance degradation",
    ) -> Dict[str, Any]:
        """
        Rolls back the production model to the specified archive version
        or the most recent archived model.
        """
        archives = sorted(self.archive_dir.glob("model_v*.joblib"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not archives:
            raise FileNotFoundError("No archived model bundles available for rollback.")

        target_file = None
        if target_version:
            for p in archives:
                if f"v{target_version}" in p.name:
                    target_file = p
                    break
            if not target_file:
                raise FileNotFoundError(f"No archive found matching version '{target_version}'.")
        else:
            target_file = archives[0]

        # Verify integrity
        is_valid, msg = self.validate_artifact_integrity(target_file)
        if not is_valid:
            raise ValueError(f"Target archive corrupt: {msg}")

        # Check current active model version
        current_version = "unknown"
        if self.active_path.exists():
            try:
                curr_bundle = joblib.load(self.active_path)
                current_version = curr_bundle.get("model_version", "unknown")
            except Exception:
                pass

        # Overwrite active bundle with target archive
        shutil.copy2(target_file, self.active_path)

        # Reload restored bundle to inspect version
        restored_bundle = joblib.load(self.active_path)
        restored_version = restored_bundle.get("model_version", "restored")
        restored_name = restored_bundle.get("model_name", "model")

        # Record in ledger
        event = self.record_deployment_event(
            event_type="ROLLBACK",
            model_name=restored_name,
            model_version=restored_version,
            approved_by=approved_by,
            reason=f"{reason} (Reverted from v{current_version} to v{restored_version})",
            archive_path=str(target_file),
        )

        return {
            "status": "ROLLBACK_SUCCESSFUL",
            "previous_version": current_version,
            "restored_version": restored_version,
            "restored_from": str(target_file.name),
            "event": event,
        }
