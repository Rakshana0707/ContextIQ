"""
enums.py

Core enumerations for the ContextIQ Model Registry (Phase 2.9).
"""

from enum import Enum


class ModelLifecycleState(str, Enum):
    """
    Formal 8-stage lifecycle states for registered models.
    Strict transitions govern progression from research to production.
    """
    DEVELOPMENT = "DEVELOPMENT"
    TRAINING = "TRAINING"
    VALIDATION = "VALIDATION"
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    PRODUCTION = "PRODUCTION"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"


class ModelFamily(str, Enum):
    """Family / architecture category of the model."""
    LINEAR = "linear"
    TREE = "tree"
    GRADIENT_BOOSTING = "gradient_boosting"
    SURVIVAL = "survival"
    ENSEMBLE = "ensemble"
    NEURAL = "neural"


class TaskType(str, Enum):
    """Prediction task type."""
    BINARY_CLASSIFICATION = "binary_classification"
    SURVIVAL_ANALYSIS = "survival_analysis"
    REGRESSION = "regression"
