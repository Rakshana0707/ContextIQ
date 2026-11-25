"""Focus window model adapter for adaptive-intelligence."""
import sys
from pathlib import Path

backend_path = str(Path(__file__).resolve().parents[3] / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.models.focus_window import UserFocusWindow

__all__ = ["UserFocusWindow"]
