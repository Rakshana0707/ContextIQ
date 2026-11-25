"""
Contextual Bandit Engine Package for Phase 4.6.
Exports:
- BanditFeatureExtractor
- LinUCBArm
- LinearThompsonSamplingArm
- BanditSafetyGuardrails, NO_ACTION_ARM
- DualLoopRewardAttributor
- OfflineBanditEvaluator
"""
from app.bandit.feature_extractor import BanditFeatureExtractor, FEATURE_DIMENSION, FEATURE_NAMES
from app.bandit.linucb import LinUCBArm
from app.bandit.offline_evaluation import OfflineBanditEvaluator
from app.bandit.reward_attribution import DualLoopRewardAttributor
from app.bandit.safety_guardrails import BanditSafetyGuardrails, NO_ACTION_ARM
from app.bandit.thompson_sampling import LinearThompsonSamplingArm

__all__ = [
    "BanditFeatureExtractor",
    "FEATURE_DIMENSION",
    "FEATURE_NAMES",
    "LinUCBArm",
    "LinearThompsonSamplingArm",
    "BanditSafetyGuardrails",
    "NO_ACTION_ARM",
    "DualLoopRewardAttributor",
    "OfflineBanditEvaluator",
]
