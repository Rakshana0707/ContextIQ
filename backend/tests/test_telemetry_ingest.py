"""Integration tests for telemetry ingestion endpoint."""
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

# Register SQLite compilation for Postgres JSONB in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models  # Register all models on Base
from app.db.session import Base, engine
from app.main import app
from app.models.telemetry_consent import UserPrivacySettings
from app.models.user import User


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_telemetry_batch_ingestion_success(client):
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(id=user_id, email=f"col_{user_id.hex[:6]}@example.com", display_name="Collector User")
        session.add(user)
        session.commit()

    payload = {
        "events": [
            {
                "event_id": "018d9f4a-0001-7000-a000-000000000001",
                "user_id": str(user_id),
                "event_type": "application_activated",
                "event_timestamp": "2026-11-22T10:00:00Z",
                "application_identifier": "code.exe",
                "payload": {"process_id": 1234},
            },
            {
                "event_id": "018d9f4a-0002-7000-a000-000000000002",
                "user_id": str(user_id),
                "event_type": "application_deactivated",
                "event_timestamp": "2026-11-22T10:05:00Z",
                "application_identifier": "code.exe",
                "payload": {"duration_seconds": 300.0},
            },
        ]
    }

    response = client.post("/api/v1/telemetry/events", json=payload, headers={"X-User-ID": str(user_id)})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 2
    assert data["accepted"] == 2
    assert data["status"] == "ok"


def test_telemetry_batch_rejected_when_user_monitoring_paused(client):
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(id=user_id, email=f"paused_{user_id.hex[:6]}@example.com", display_name="Paused User")
        session.add(user)
        # Set user privacy settings to paused
        settings = UserPrivacySettings(
            user_id=user_id,
            is_paused=True,
        )
        session.add(settings)
        session.commit()

    payload = {
        "events": [
            {
                "event_id": "018d9f4a-0003-7000-a000-000000000003",
                "user_id": str(user_id),
                "event_type": "application_activated",
                "event_timestamp": "2026-11-22T10:00:00Z",
                "application_identifier": "code.exe",
                "payload": {},
            }
        ]
    }

    response = client.post("/api/v1/telemetry/events", json=payload, headers={"X-User-ID": str(user_id)})
    assert response.status_code == 403
    assert "paused" in response.json()["detail"].lower()
