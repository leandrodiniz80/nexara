import uuid

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.application_services import get_workspace_application_service
from app.models.mission.enums import MissionPriority, MissionStatus
from tests.application.services.test_workspace_application_service import (
    _build_service as build_workspace_application_service,
)


def _client_and_repos():
    service, repos = build_workspace_application_service()
    app = create_app()
    app.dependency_overrides[get_workspace_application_service] = lambda: service
    return TestClient(app), repos


async def test_load_mission_workspace_returns_shaped_response():
    client, repos = _client_and_repos()
    mission = await repos["mission_repository"].create(
        name="Expansão Goiânia",
        status=MissionStatus.RUNNING,
        priority=MissionPriority.NORMAL,
    )

    response = client.get(f"/api/v1/workspace/missions/{mission.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["mission"]["name"] == "Expansão Goiânia"


def test_load_mission_workspace_for_unknown_mission_returns_success_false():
    client, _ = _client_and_repos()

    response = client.get(f"/api/v1/workspace/missions/{uuid.uuid4()}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert any("not found" in error["message"] for error in body["errors"])
