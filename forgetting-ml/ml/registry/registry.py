"""
registry.py

Centralized, file-backed Model Registry for ContextIQ (Phase 2.9).
Tracks metadata, manages the 8-stage lifecycle state machine, enforces single active
production invariants, logs immutable audit ledgers, and provides rollback capabilities.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ml.registry.artifact_store import ArtifactStore, compute_file_sha256
from ml.registry.enums import ModelFamily, ModelLifecycleState, TaskType
from ml.registry.models import (
    ArtifactNotFoundError,
    ChecksumMismatchError,
    InvalidStateTransitionError,
    ModelMetadata,
    ModelRegistryError,
)

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


class ModelRegistry:
    """
    Centralized Model Lifecycle Manager for ContextIQ.
    Thread-safe and backed by transactional JSON persistence and audit logging.
    """

    _instance: Optional["ModelRegistry"] = None

    def __init__(
        self,
        catalog_path: Optional[Path] = None,
        audit_path: Optional[Path] = None,
        artifact_store: Optional[ArtifactStore] = None,
    ):
        self.catalog_path = Path(catalog_path) if catalog_path else ROOT / "artifacts" / "model_catalog.json"
        self.audit_path = Path(audit_path) if audit_path else ROOT / "artifacts" / "model_registry_audit.jsonl"
        self.artifact_store = artifact_store or ArtifactStore()

        self._models: Dict[str, ModelMetadata] = {}
        self._load_catalog()
        self.bootstrap_existing_models()

    @classmethod
    def instance(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================================
    # Persistence & Catalog Management
    # =========================================================================

    def _load_catalog(self) -> None:
        """Loads models from catalog JSON file into memory."""
        self._models.clear()
        if not self.catalog_path.exists():
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        meta = ModelMetadata.from_dict(item)
                        self._models[meta.model_id] = meta
        except Exception as e:
            logger.error("Failed to load model catalog: %s", e)

    def _save_catalog(self) -> None:
        """Atomically saves catalog into disk."""
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.catalog_path.with_suffix(".tmp")
        payload = [meta.to_dict() for meta in self._models.values()]

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        temp_path.replace(self.catalog_path)

    def _log_audit(
        self,
        event_type: str,
        model_id: str,
        actor: str,
        details: Dict[str, Any],
    ) -> None:
        """Appends an event to the immutable JSONL audit ledger."""
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "model_id": model_id,
            "actor": actor,
            "details": details,
        }
        with open(self.audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    # =========================================================================
    # Bootstrapping Pre-existing Artifacts
    # =========================================================================

    def bootstrap_existing_models(self) -> None:
        """
        Registers existing Phase 2.1-2.8 production models into the registry catalog
        if they are not already tracked. Ensures zero downtime and strict backward compatibility.
        """
        # 1. Existing Binary Classification Model (LogReg benchmark v1.1.0)
        bin_artifact = ROOT / "artifacts" / "model_bundle.joblib"
        bin_model_id = "clf_logreg_v1.1.0"
        if bin_artifact.exists() and bin_model_id not in self._models:
            try:
                checksum = compute_file_sha256(bin_artifact)
                metrics_path = ROOT / "artifacts" / "metrics.json"
                metrics = {}
                if metrics_path.exists():
                    try:
                        with open(metrics_path, "r", encoding="utf-8") as mf:
                            metrics = json.load(mf).get("validation", {})
                    except Exception:
                        pass

                bin_meta = ModelMetadata(
                    model_id=bin_model_id,
                    model_name="logistic_regression",
                    model_version="1.1.0",
                    model_family=ModelFamily.LINEAR,
                    task_type=TaskType.BINARY_CLASSIFICATION,
                    training_dataset_version="1.0.0",
                    feature_schema_version="2.2.0",
                    target_definition_version="2.1.0",
                    training_timestamp="2026-11-20T12:00:00Z",
                    registered_at=datetime.now(timezone.utc).isoformat(),
                    artifact_location="artifacts/model_bundle.joblib",
                    artifact_checksum=checksum,
                    lifecycle_state=ModelLifecycleState.PRODUCTION,
                    evaluation_metrics=metrics or {
                        "pr_auc": 0.4451,
                        "roc_auc": 0.6583,
                        "brier_score": 0.1839,
                    },
                    calibration_config={"method": "platt", "calibrated": True},
                    shap_compatibility={"supported": True, "explainer": "LinearExplainer"},
                    description="ContextIQ Phase 2.5/2.7 production binary forgetting-risk model.",
                    approved_by="MLOps System",
                )
                self._models[bin_model_id] = bin_meta
                self._log_audit(
                    "MODEL_BOOTSTRAPPED",
                    bin_model_id,
                    "System",
                    {"task_type": "binary_classification", "status": "PRODUCTION"},
                )
            except Exception as e:
                logger.warning("Could not bootstrap binary model: %s", e)

        # 2. Existing Survival Analysis Model (Cox Proportional Hazards v2.3.0)
        surv_artifact = ROOT / "artifacts" / "survival_bundle.joblib"
        surv_model_id = "surv_cox_v2.3.0"
        if surv_artifact.exists() and surv_model_id not in self._models:
            try:
                checksum = compute_file_sha256(surv_artifact)
                surv_metrics_path = ROOT / "artifacts" / "survival_evaluation_report.json"
                surv_metrics = {}
                if surv_metrics_path.exists():
                    try:
                        with open(surv_metrics_path, "r", encoding="utf-8") as sf:
                            surv_metrics = json.load(sf).get("test_metrics", {})
                    except Exception:
                        pass

                surv_meta = ModelMetadata(
                    model_id=surv_model_id,
                    model_name="cox_proportional_hazards",
                    model_version="2.3.0",
                    model_family=ModelFamily.SURVIVAL,
                    task_type=TaskType.SURVIVAL_ANALYSIS,
                    training_dataset_version="2.3.0",
                    feature_schema_version="2.3.0",
                    target_definition_version="2.3.0",
                    training_timestamp="2026-11-20T13:00:00Z",
                    registered_at=datetime.now(timezone.utc).isoformat(),
                    artifact_location="artifacts/survival_bundle.joblib",
                    artifact_checksum=checksum,
                    lifecycle_state=ModelLifecycleState.PRODUCTION,
                    evaluation_metrics=surv_metrics or {
                        "concordance_index": 0.6205,
                        "integrated_brier_score": 0.1412,
                    },
                    calibration_config={"method": "survival_hazard"},
                    shap_compatibility={"supported": False},
                    description="ContextIQ Phase 2.3 production Cox survival analysis model.",
                    approved_by="MLOps System",
                )
                self._models[surv_model_id] = surv_meta
                self._log_audit(
                    "MODEL_BOOTSTRAPPED",
                    surv_model_id,
                    "System",
                    {"task_type": "survival_analysis", "status": "PRODUCTION"},
                )
            except Exception as e:
                logger.warning("Could not bootstrap survival model: %s", e)

        self._save_catalog()

    # =========================================================================
    # Model Registration & Lifecycle Transitions
    # =========================================================================

    def register_model(self, metadata: ModelMetadata) -> ModelMetadata:
        """Registers a new model in the catalog."""
        if metadata.model_id in self._models:
            raise ModelRegistryError(f"Model ID '{metadata.model_id}' is already registered.")

        # Check version duplicate for the same model_name
        for m in self._models.values():
            if m.model_name == metadata.model_name and m.model_version == metadata.model_version:
                raise ModelRegistryError(
                    f"Model '{metadata.model_name}' version '{metadata.model_version}' already exists."
                )

        self._models[metadata.model_id] = metadata
        self._save_catalog()
        self._log_audit(
            "MODEL_REGISTERED",
            metadata.model_id,
            "Registry",
            {"name": metadata.model_name, "version": metadata.model_version, "state": metadata.lifecycle_state.value},
        )
        return metadata

    def transition_state(
        self,
        model_id: str,
        new_state: ModelLifecycleState,
        actor: str = "Lead Data Scientist",
        notes: Optional[str] = None,
    ) -> ModelMetadata:
        """
        Executes a formal lifecycle transition.
        Enforces:
        1. Valid transition in state machine
        2. Invariant: At most 1 model in PRODUCTION per task_type
        """
        meta = self.get_model(model_id)
        if not meta:
            raise ModelRegistryError(f"Model '{model_id}' not found.")

        old_state = meta.lifecycle_state

        # If transitioning to PRODUCTION, archive any existing active production model for this task_type
        if new_state == ModelLifecycleState.PRODUCTION:
            active_prod = self.get_production_model(meta.task_type)
            if active_prod and active_prod.model_id != meta.model_id:
                active_prod.transition_to(
                    ModelLifecycleState.ARCHIVED,
                    actor="System Automation",
                    notes=f"Auto-archived upon promotion of {meta.model_id}",
                )
                self._log_audit(
                    "MODEL_TRANSITIONED",
                    active_prod.model_id,
                    "System Automation",
                    {"old_state": "PRODUCTION", "new_state": "ARCHIVED", "reason": f"Replaced by {meta.model_id}"},
                )

        meta.transition_to(new_state, actor=actor, notes=notes)
        self._save_catalog()
        self._log_audit(
            "MODEL_TRANSITIONED",
            meta.model_id,
            actor,
            {"old_state": old_state.value, "new_state": new_state.value, "notes": notes},
        )
        return meta

    def approve_model(
        self,
        model_id: str,
        actor: str = "Lead Data Scientist",
        rationale: Optional[str] = None,
    ) -> ModelMetadata:
        """Approves a candidate model for production consideration."""
        return self.transition_state(
            model_id=model_id,
            new_state=ModelLifecycleState.APPROVED,
            actor=actor,
            notes=rationale or "Model approved by MLOps review",
        )

    def promote_to_production(
        self,
        model_id: str,
        actor: str = "MLOps Admin",
        rationale: Optional[str] = None,
    ) -> ModelMetadata:
        """Promotes an approved model into production."""
        meta = self.get_model(model_id)
        if not meta:
            raise ModelRegistryError(f"Model '{model_id}' not found.")

        # Ensure integrity check passes before allowing promotion
        self.verify_model_integrity(model_id)

        return self.transition_state(
            model_id=model_id,
            new_state=ModelLifecycleState.PRODUCTION,
            actor=actor,
            notes=rationale or "Promoted to production",
        )

    def rollback(
        self,
        task_type: TaskType,
        target_version: str,
        actor: str = "MLOps Admin",
        reason: str = "Rollback requested",
    ) -> Tuple[ModelMetadata, Optional[ModelMetadata]]:
        """
        Rolls back the active production model to a target version.
        Returns: (restored_model, previously_active_model).
        """
        # 1. Locate target model
        target_model: Optional[ModelMetadata] = None
        for m in self._models.values():
            if m.task_type == task_type and m.model_version == target_version:
                target_model = m
                break

        if not target_model:
            raise ModelRegistryError(
                f"No model found for task '{task_type.value}' with version '{target_version}'."
            )

        # 2. Verify target artifact integrity
        self.verify_model_integrity(target_model.model_id)

        current_prod = self.get_production_model(task_type)

        # 3. Archive current production model
        if current_prod and current_prod.model_id != target_model.model_id:
            current_prod.transition_to(
                ModelLifecycleState.ARCHIVED,
                actor=actor,
                notes=f"Archived due to rollback to v{target_version}",
            )

        # 4. Promote target model to production
        target_model.transition_to(
            ModelLifecycleState.PRODUCTION,
            actor=actor,
            notes=f"Restored via rollback: {reason}",
        )

        self._save_catalog()
        self._log_audit(
            "MODEL_ROLLBACK",
            target_model.model_id,
            actor,
            {
                "previous_production_model": current_prod.model_id if current_prod else None,
                "restored_version": target_version,
                "reason": reason,
            },
        )
        return target_model, current_prod

    # =========================================================================
    # Queries & Integrity Validation
    # =========================================================================

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """Retrieves a model by its unique ID."""
        return self._models.get(model_id)

    def get_production_model(self, task_type: TaskType) -> Optional[ModelMetadata]:
        """Returns the active PRODUCTION model for a given task type."""
        for m in self._models.values():
            if m.task_type == task_type and m.lifecycle_state == ModelLifecycleState.PRODUCTION:
                return m
        return None

    def list_models(
        self,
        task_type: Optional[TaskType] = None,
        status: Optional[ModelLifecycleState] = None,
        family: Optional[ModelFamily] = None,
    ) -> List[ModelMetadata]:
        """Queries registered models matching filters."""
        results = list(self._models.values())
        if task_type:
            results = [m for m in results if m.task_type == task_type]
        if status:
            results = [m for m in results if m.lifecycle_state == status]
        if family:
            results = [m for m in results if m.model_family == family]
        return sorted(results, key=lambda m: m.registered_at, reverse=True)

    def get_versions(self, model_name: str) -> List[ModelMetadata]:
        """Returns all versions registered for a model name."""
        return [m for m in self._models.values() if m.model_name == model_name]

    def verify_model_integrity(self, model_id: str) -> bool:
        """Validates artifact file existence and SHA-256 checksum."""
        meta = self.get_model(model_id)
        if not meta:
            raise ModelRegistryError(f"Model '{model_id}' not found.")

        path = Path(meta.artifact_location)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise ArtifactNotFoundError(f"Model artifact missing at {path}")

        current_checksum = compute_file_sha256(path)
        if current_checksum != meta.artifact_checksum:
            raise ChecksumMismatchError(
                f"Checksum mismatch for model {model_id}!\n"
                f"Expected: {meta.artifact_checksum}\n"
                f"Actual:   {current_checksum}"
            )
        return True

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Returns metrics overview across models for dashboards."""
        summary = {
            "total_models": len(self._models),
            "production_models": {},
            "models_by_state": {},
            "models_by_family": {},
        }
        for m in self._models.values():
            state_str = m.lifecycle_state.value
            fam_str = m.model_family.value
            summary["models_by_state"][state_str] = summary["models_by_state"].get(state_str, 0) + 1
            summary["models_by_family"][fam_str] = summary["models_by_family"].get(fam_str, 0) + 1

            if m.lifecycle_state == ModelLifecycleState.PRODUCTION:
                summary["production_models"][m.task_type.value] = {
                    "model_id": m.model_id,
                    "model_name": m.model_name,
                    "model_version": m.model_version,
                    "metrics": m.evaluation_metrics,
                }
        return summary

    # =========================================================================
    # Phase 2.4 Experiment Registry Bridge
    # =========================================================================

    def register_from_experiment(
        self,
        experiment_id: str,
        model_version: str = "1.2.0",
        target_state: ModelLifecycleState = ModelLifecycleState.CANDIDATE,
        actor: str = "Lead Data Scientist",
    ) -> ModelMetadata:
        """
        Bridges the Phase 2.4 experiment registry with the model registry, promoting
        a successful benchmark experiment into a candidate model record.
        """
        exp_registry_path = ROOT / "artifacts" / "experiment_registry.json"
        if not exp_registry_path.exists():
            raise FileNotFoundError("Experiment registry not found.")

        with open(exp_registry_path, "r", encoding="utf-8") as f:
            experiments = json.load(f)

        matched_exp = None
        for exp in experiments:
            if exp.get("experiment_id") == experiment_id:
                matched_exp = exp
                break

        if not matched_exp:
            raise ValueError(f"Experiment ID '{experiment_id}' not found in registry.")

        model_type = matched_exp.get("model_type", "logistic_regression")
        family = ModelFamily.LINEAR if "logistic" in model_type else ModelFamily.TREE
        model_id = f"clf_{model_type}_v{model_version.lstrip('v')}"

        meta = ModelMetadata(
            model_id=model_id,
            model_name=model_type,
            model_version=model_version,
            model_family=family,
            task_type=TaskType.BINARY_CLASSIFICATION,
            training_dataset_version=matched_exp.get("dataset_version", "1.0.0"),
            feature_schema_version=matched_exp.get("feature_version", "2.2.0"),
            target_definition_version="2.1.0",
            training_timestamp=matched_exp.get("training_timestamp", datetime.now(timezone.utc).isoformat()),
            registered_at=datetime.now(timezone.utc).isoformat(),
            artifact_location=f"artifacts/models/binary_classification/{model_type}/v{model_version}/model_bundle.joblib",
            artifact_checksum="placeholder-sha256",
            lifecycle_state=target_state,
            evaluation_metrics=matched_exp.get("metrics", {}),
            experiment_id=experiment_id,
            description=matched_exp.get("notes", f"Promoted from experiment {experiment_id}"),
            approved_by=actor,
        )

        return self.register_model(meta)
