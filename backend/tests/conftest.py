import pytest

from app.api.routers import auth as auth_router
from app.core.config import settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _open_registration(monkeypatch):
    # The suite builds its users through POST /auth/register anonymously
    # (including joining existing organizations), so it runs in the legacy
    # "open" mode. Production defaults to "invite" — covered explicitly in
    # tests/api/test_register_hardening.py, which switches the mode back.
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "open")
    auth_router._register_rate_limiter._requests.clear()
