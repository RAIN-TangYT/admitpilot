import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # type: ignore[import-not-found]

from admitpilot.api.main import create_api_app
from admitpilot.app import build_application
from admitpilot.config import AdmitPilotSettings


def test_api_health_and_ready_endpoints_return_ok_status() -> None:
    settings = AdmitPilotSettings(run_mode="test")
    application = build_application(settings=settings)
    api_app = create_api_app(settings=settings, application=application)
    client = TestClient(api_app)

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "admitpilot", "mode": "test"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "service": "admitpilot", "mode": "test"}
