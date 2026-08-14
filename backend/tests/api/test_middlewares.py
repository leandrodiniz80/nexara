import logging
import uuid

from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_request_id_is_generated_when_not_provided():
    client = _client()

    response = client.get("/health")

    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    uuid.UUID(request_id)  # raises if it isn't a real UUID


def test_request_id_is_echoed_back_when_client_provides_one():
    client = _client()
    given_id = str(uuid.uuid4())

    response = client.get("/health", headers={"X-Request-ID": given_id})

    assert response.headers["X-Request-ID"] == given_id
    assert response.json()["request_id"] == given_id


def test_each_request_gets_a_different_request_id_by_default():
    client = _client()

    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]

    assert first != second


def test_timing_header_is_present_and_non_negative():
    client = _client()

    response = client.get("/health")

    execution_time = float(response.headers["X-Execution-Time"])
    assert execution_time >= 0
    assert response.json()["execution_time"] >= 0


def test_logging_middleware_records_method_route_status_and_request_id(caplog):
    client = _client()

    with caplog.at_level(logging.INFO, logger="app.api.requests"):
        response = client.get("/health")

    request_id = response.headers["X-Request-ID"]
    records = [r for r in caplog.records if r.name == "app.api.requests"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "GET" in message
    assert "/health" in message
    assert "200" in message
    assert request_id in message
