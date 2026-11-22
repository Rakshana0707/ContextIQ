"""Pytest fixtures and mock providers for desktop agent tests."""
import sys
from pathlib import Path

# Ensure desktop-agent is on sys.path
agent_dir = Path(__file__).resolve().parent.parent
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))
