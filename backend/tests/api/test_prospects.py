import uuid

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.application_services import get_prospect_application_service
from tests.application.services.test_prospect_application_service import (
    _build_service as build_prospect_application_service,
    _company as company_payload,
)


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_prospect_application_service] = build_prospect_application_service
    return TestClient(app)


def test_qualify_prospect_returns_analysis_result():
    client = _client()
    prospect_id = uuid.uuid4()

    response = client.post(
        f"/api/v1/prospects/{prospect_id}/qualify",
        json={"profile": {"segment": "retail", "company_size": "small"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert 0 <= body["data"]["score"]["total_score"] <= 100


def test_generate_prospect_asset_returns_pending_approval():
    client = _client()
    prospect_id = uuid.uuid4()
    company = company_payload().model_dump(mode="json")

    response = client.post(
        f"/api/v1/prospects/{prospect_id}/generate-asset",
        json={
            "company": company,
            "asset_type": "email",
            "tone": "consultivo",
            "contact_name": "João",
            "objective": "Conseguir reunião",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "pending_approval"


def test_approve_then_reject_asset_lifecycle():
    client = _client()
    prospect_id = uuid.uuid4()
    company = company_payload().model_dump(mode="json")
    generated = client.post(
        f"/api/v1/prospects/{prospect_id}/generate-asset",
        json={"company": company, "asset_type": "email"},
    ).json()
    asset_id = generated["data"]["id"]

    approved = client.post(
        f"/api/v1/prospects/{prospect_id}/approve-asset",
        json={"asset_id": asset_id},
    ).json()
    assert approved["success"] is True
    assert approved["data"]["status"] == "approved"


def test_approve_unknown_asset_returns_success_false():
    client = _client()

    response = client.post(
        f"/api/v1/prospects/{uuid.uuid4()}/approve-asset",
        json={"asset_id": str(uuid.uuid4())},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert any("not found" in error["message"] for error in body["errors"])


def test_qualify_with_invalid_body_returns_422():
    client = _client()

    response = client.post(
        f"/api/v1/prospects/{uuid.uuid4()}/qualify",
        json={"profile": {"segment": "not-a-real-segment", "company_size": "small"}},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
