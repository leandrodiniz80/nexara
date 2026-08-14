import uuid

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.application_services import get_mission_application_service
from tests.application.services.test_mission_application_service import (
    _build_service as build_mission_application_service,
)


def _client_and_service():
    service = build_mission_application_service()
    app = create_app()
    app.dependency_overrides[get_mission_application_service] = lambda: service
    return TestClient(app), service


def _client() -> TestClient:
    client, _ = _client_and_service()
    return client


def _mission_body(**overrides) -> dict:
    body = dict(
        mission_name="Expansão Goiânia",
        segment="Publicidade",
        city="Goiânia",
        minimum_score=0,
        asset_type="email",
    )
    body.update(overrides)
    return body


def test_start_mission_returns_shaped_response():
    client = _client()

    response = client.post("/api/v1/missions", json=_mission_body())

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"]["mission"]["name"] == "Expansão Goiânia"
    assert body["request_id"]


def test_start_mission_with_blank_name_returns_success_false_not_a_500():
    client = _client()

    response = client.post("/api/v1/missions", json=_mission_body(mission_name="   "))

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert any("mission_name" in error["message"] for error in body["errors"])


def test_start_mission_with_missing_required_field_returns_422_validation_error():
    client = _client()

    response = client.post("/api/v1/missions", json={"mission_name": "X"})

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "validation_error"


async def test_mission_lifecycle_pause_resume_cancel():
    client, service = _client_and_service()
    created = client.post("/api/v1/missions", json=_mission_body()).json()
    mission_id = uuid.UUID(created["data"]["summary"]["mission"]["id"])

    # a freshly-created mission is DRAFT; pause() requires RUNNING, so this test
    # moves it there directly through the service's own MissionEngine — starting a
    # *new* mission and resuming a *paused* one are different HTTP operations.
    draft_mission = await service.mission_engine.repository.get_by_id(mission_id)
    await service.mission_engine.start(draft_mission)

    paused = client.post(f"/api/v1/missions/{mission_id}/pause", json={}).json()
    assert paused["success"] is True
    assert paused["data"]["status"] == "paused"

    resumed = client.post(f"/api/v1/missions/{mission_id}/resume", json={}).json()
    assert resumed["data"]["status"] == "running"

    cancelled = client.post(
        f"/api/v1/missions/{mission_id}/cancel", json={"reason": "Cliente desistiu"}
    ).json()
    assert cancelled["data"]["status"] == "cancelled"


def test_pause_unknown_mission_returns_success_false_not_a_500():
    client = _client()

    response = client.post(f"/api/v1/missions/{uuid.uuid4()}/pause", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert any("not found" in error["message"] for error in body["errors"])


def test_get_mission_status_for_unknown_mission_returns_success_false():
    client = _client()

    response = client.get(f"/api/v1/missions/{uuid.uuid4()}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert any("not found" in error["message"] for error in body["errors"])


def test_get_mission_status_returns_workspace_data():
    client = _client()
    created = client.post("/api/v1/missions", json=_mission_body()).json()
    mission_id = created["data"]["summary"]["mission"]["id"]

    response = client.get(f"/api/v1/missions/{mission_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["mission"]["id"] == mission_id
