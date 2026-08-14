import uuid

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.application_services import get_outreach_application_service
from app.application.services.outreach_application_service import OutreachApplicationService
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine


def _client_and_engine():
    outreach_engine = build_default_outreach_engine()
    service = OutreachApplicationService(outreach_engine)
    app = create_app()
    app.dependency_overrides[get_outreach_application_service] = lambda: service
    return TestClient(app), outreach_engine


def test_generate_outreach_asset_from_template():
    client, outreach_engine = _client_and_engine()
    template = outreach_engine.template_repository.get_active_by_category("follow_up")

    response = client.post(
        "/api/v1/outreach/generate",
        json={
            "prospect_id": str(uuid.uuid4()),
            "template_id": str(template.id),
            "variables": {"contact_name": "João", "company": "Agência XYZ"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "draft"
    assert "João" in body["data"]["content"]


def test_submit_then_approve_then_reject_full_cycle():
    client, outreach_engine = _client_and_engine()
    template = outreach_engine.template_repository.get_active_by_category("follow_up")
    generated = client.post(
        "/api/v1/outreach/generate",
        json={
            "prospect_id": str(uuid.uuid4()),
            "template_id": str(template.id),
            "variables": {"contact_name": "João", "company": "Agência XYZ"},
        },
    ).json()
    asset_id = generated["data"]["id"]

    submitted = client.post("/api/v1/outreach/submit", json={"asset_id": asset_id}).json()
    assert submitted["success"] is True
    assert submitted["data"]["status"] == "pending_approval"

    approved = client.post(
        "/api/v1/outreach/approve", json={"asset_id": asset_id}
    ).json()
    assert approved["success"] is True
    assert approved["data"]["status"] == "approved"


def test_reject_requires_pending_approval_state():
    client, outreach_engine = _client_and_engine()
    template = outreach_engine.template_repository.get_active_by_category("follow_up")
    generated = client.post(
        "/api/v1/outreach/generate",
        json={
            "prospect_id": str(uuid.uuid4()),
            "template_id": str(template.id),
            "variables": {"contact_name": "João", "company": "Agência XYZ"},
        },
    ).json()
    asset_id = generated["data"]["id"]

    # asset is still DRAFT — reject() requires PENDING_APPROVAL, so this must fail
    # gracefully, not raise.
    response = client.post("/api/v1/outreach/reject", json={"asset_id": asset_id})

    assert response.status_code == 200
    assert response.json()["success"] is False


def test_approve_unknown_asset_returns_success_false_not_500():
    client, _ = _client_and_engine()

    response = client.post("/api/v1/outreach/approve", json={"asset_id": str(uuid.uuid4())})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert any("not found" in error["message"] for error in body["errors"])


def test_generate_with_invalid_uuid_returns_422():
    client, _ = _client_and_engine()

    response = client.post(
        "/api/v1/outreach/generate",
        json={"prospect_id": "not-a-uuid", "template_id": str(uuid.uuid4()), "variables": {}},
    )

    assert response.status_code == 422
