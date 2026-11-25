"""Adaptive intelligence focus window schemas adapter."""
import sys
from pathlib import Path

backend_path = str(Path(__file__).resolve().parents[3] / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.schemas.focus_window import (
    HourlyTemporalMetrics,
    FocusWindowItemRead,
    CategoryFocusWindowRead,
    FocusWindowMetricsResponse,
)

__all__ = [
    "HourlyTemporalMetrics",
    "FocusWindowItemRead",
    "CategoryFocusWindowRead",
    "FocusWindowMetricsResponse",
]
