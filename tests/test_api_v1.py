from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from admitpilot.api.main import create_api_app
from admitpilot.app import build_application
from admitpilot.config import AdmitPilotSettings


def _client() -> TestClient:
    data_path = Path(".pytest-local") / f"api_v1_{uuid4().hex}.sqlite3"
    settings = AdmitPilotSettings(run_mode="test", api_data_path=str(data_path))
    application = build_application(settings=settings)
    api_app = create_api_app(settings=settings, application=application)
    return TestClient(api_app)


def _auth_headers(client: TestClient) -> dict[str, str]:
    token = _auth_token(client)
    return {"Authorization": f"Bearer {token}"}


def _auth_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@admitpilot.local", "password": "admitpilot-demo"},
    )
    assert response.status_code == 200
    return str(response.json()["token"])


def test_catalog_returns_supported_schools_and_default_portfolio() -> None:
    client = _client()

    response = client.get("/api/v1/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["schools"]) == 5
    assert payload["default_portfolio"]["NUS"] == "MCOMP_CS"


def test_demo_profile_returns_complete_profile_and_user_artifacts() -> None:
    client = _client()

    response = client.get("/api/v1/demo-profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["academic_metrics"]["gpa"] > 0
    assert payload["profile"]["language_scores"]["ielts"] > 0
    assert payload["profile"]["experiences"]
    assert payload["constraints"]["user_artifacts"]


def test_profile_validate_returns_required_fields_for_empty_profile() -> None:
    client = _client()

    response = client.post("/api/v1/profile/validate", json={"profile": {}})

    assert response.status_code == 200
    payload = response.json()
    missing_keys = {item["key"] for item in payload["missing_profile_fields"]}
    assert payload["status"] == "needs_profile_input"
    assert "academic_metrics.gpa" in missing_keys
    assert "language_scores" in missing_keys
    assert "experiences" in missing_keys


def test_auth_login_returns_demo_user_and_me() -> None:
    client = _client()
    headers = _auth_headers(client)

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "demo@admitpilot.local"


def test_orchestration_requires_authentication() -> None:
    client = _client()
    demo_payload = client.get("/api/v1/demo-profile").json()

    response = client.post("/api/v1/orchestrations", json=demo_payload)

    assert response.status_code == 401


def test_orchestration_returns_needs_profile_input_for_incomplete_profile() -> None:
    client = _client()
    headers = _auth_headers(client)

    response = client.post(
        "/api/v1/orchestrations",
        json={"user_query": "demo", "profile": {"degree_level": "bachelor"}},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_profile_input"
    assert payload["results"] == []
    assert payload["run_id"].startswith("run_")


def test_orchestration_returns_four_successful_agents_for_demo_profile() -> None:
    client = _client()
    headers = _auth_headers(client)
    demo_payload = client.get("/api/v1/demo-profile").json()

    response = client.post("/api/v1/orchestrations", json=demo_payload, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "delivered"
    assert payload["missing_profile_fields"] == []
    assert {item["agent"] for item in payload["results"]} == {"aie", "sae", "dta", "cds"}
    assert all(item["status"] == "SUCCESS" for item in payload["results"])
    assert payload["run_id"].startswith("run_")


def test_orchestration_websocket_streams_real_agent_stage_events() -> None:
    client = _client()
    token = _auth_token(client)
    demo_payload = client.get("/api/v1/demo-profile").json()

    with client.websocket_connect(f"/api/v1/orchestrations/ws?token={token}") as websocket:
        websocket.send_json(demo_payload)
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event)
            if event["event"] == "workflow_completed":
                break

    event_names = [item["event"] for item in events]
    assert event_names[0] == "workflow_started"
    assert event_names.count("stage_started") == 4
    assert event_names.count("stage_completed") == 4
    completed_agents = [
        item["data"]["agent"] for item in events if item["event"] == "stage_completed"
    ]
    assert completed_agents == ["aie", "sae", "dta", "cds"]
    response_payload = events[-1]["data"]["response"]
    assert response_payload["status"] == "delivered"
    assert response_payload["run_id"].startswith("run_")


def test_run_history_persists_orchestration_response() -> None:
    client = _client()
    headers = _auth_headers(client)
    demo_payload = client.get("/api/v1/demo-profile").json()
    run_payload = client.post(
        "/api/v1/orchestrations",
        json=demo_payload,
        headers=headers,
    ).json()

    history_response = client.get("/api/v1/runs", headers=headers)

    assert history_response.status_code == 200
    runs = history_response.json()["runs"]
    assert runs[0]["run_id"] == run_payload["run_id"]
    detail_response = client.get(f"/api/v1/runs/{run_payload['run_id']}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()["run"]
    assert detail["response"]["trace_id"] == run_payload["trace_id"]
    assert detail["response"]["run_id"] == run_payload["run_id"]


def test_run_history_delete_removes_run_for_current_user() -> None:
    client = _client()
    headers = _auth_headers(client)
    demo_payload = client.get("/api/v1/demo-profile").json()
    run_payload = client.post(
        "/api/v1/orchestrations",
        json=demo_payload,
        headers=headers,
    ).json()

    delete_response = client.delete(f"/api/v1/runs/{run_payload['run_id']}", headers=headers)

    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"
    history_response = client.get("/api/v1/runs", headers=headers)
    assert history_response.json()["runs"] == []
    detail_response = client.get(f"/api/v1/runs/{run_payload['run_id']}", headers=headers)
    assert detail_response.status_code == 404
