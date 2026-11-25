"""
Internal behavioral profile models for adaptive-intelligence.
Re-exports from backend models or defines SQLAlchemy models.
"""
import sys
from pathlib import Path

# Add backend to sys.path so we can share models
backend_path = str(Path(__file__).resolve().parents[3] / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.models.behavioral_profile import (
    UserBehavioralProfile,
    ProfileSnapshot,
    ProfileAuditLog,
)

__all__ = [
    "UserBehavioralProfile",
    "ProfileSnapshot",
    "ProfileAuditLog",
]
