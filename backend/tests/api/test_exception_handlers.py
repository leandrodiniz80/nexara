import uuid

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.application_services import get_prospect_application_service


def _client() -> TestClient:
    return TestClient(create_app())


def test_unmatched_route_returns_404_in_the_api_response_envelope():
    client = _client()

    response = client.get("/api/v1/this-route-does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "not_found"
    assert "request_id" in body


def test_invalid_body_returns_422_validation_error_with_details():
    client = _client()

    response = client.post(
        "/api/v1/prospects/00000000-0000-0000-0000-000000000000/qualify",
        json={"profile": {"segment": "not-a-real-segment"}},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    error = body["errors"][0]
    assert error["code"] == "validation_error"
    assert error["details"] is not None


def test_unexpected_exception_from_a_dependency_returns_500_without_leaking_it():
    app = create_app()

    def _broken_dependency():
        raise RuntimeError("something exploded deep inside a real dependency")

    app.dependency_overrides[get_prospect_application_service] = _broken_dependency
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        f"/api/v1/prospects/{uuid.uuid4()}/qualify",
        json={"profile": {"segment": "retail", "company_size": "small"}},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    error = body["errors"][0]
    assert error["code"] == "internal_error"
    # never leak the real exception message or a traceback
    assert "something exploded" not in body["errors"][0]["message"]
    assert "RuntimeError" not in str(body)
    assert "Traceback" not in str(body)


def test_every_error_response_still_uses_the_api_response_envelope():
    client = _client()

    response = client.get("/api/v1/this-route-does-not-exist")

    body = response.json()
    assert set(body.keys()) == {
        "success",
        "data",
        "errors",
        "warnings",
        "request_id",
        "execution_time",
        "timestamp",
    }
    assert body["data"] is None
