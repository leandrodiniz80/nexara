from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_branding_endpoint():
    client = _client()

    response = client.get("/api/v1/branding")

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["name"] == "Nexara"
    assert "theme" in data
    assert "colors" in data["theme"]
    assert "typography" in data["theme"]
    assert "spacing" in data["theme"]


def test_branding_nao_exige_autenticacao():
    client = _client()

    response = client.get("/api/v1/branding")

    assert response.status_code == 200


def test_branding_usa_o_envelope_api_response():
    client = _client()

    body = client.get("/api/v1/branding").json()

    assert set(body.keys()) == {
        "success",
        "data",
        "errors",
        "warnings",
        "request_id",
        "execution_time",
        "timestamp",
    }
    assert body["success"] is True
    assert body["errors"] == []


def test_branding_retorna_todas_as_cores_esperadas():
    client = _client()

    colors = client.get("/api/v1/branding").json()["data"]["theme"]["colors"]

    assert colors["primary_bg"] == "#0B0F1A"
    assert colors["secondary_bg"] == "#121826"
    assert colors["border"] == "#1F2A44"
    assert colors["text_primary"] == "#E6EAF2"
    assert colors["text_secondary"] == "#9AA4BF"
    assert colors["text_muted"] == "#6B7280"
    assert colors["accent_primary"] == "#6366F1"
    assert colors["accent_success"] == "#22C55E"
    assert colors["accent_warning"] == "#F59E0B"
    assert colors["accent_danger"] == "#EF4444"
    assert colors["accent_info"] == "#3B82F6"
    assert colors["gradient_main"] == "linear-gradient(135deg, #6366F1, #8B5CF6, #3B82F6)"


def test_branding_retorna_tipografia_esperada():
    client = _client()

    typography = client.get("/api/v1/branding").json()["data"]["theme"]["typography"]

    assert typography["font_family"] == "Inter, system-ui, sans-serif"
    assert typography["font_size_base"] == 14
    assert typography["font_weight_regular"] == 400
    assert typography["font_weight_bold"] == 600


def test_branding_retorna_spacing_esperado():
    client = _client()

    spacing = client.get("/api/v1/branding").json()["data"]["theme"]["spacing"]

    assert spacing == {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}


def test_branding_response_inclui_request_id_header():
    client = _client()

    response = client.get("/api/v1/branding")

    assert "X-Request-ID" in response.headers
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
