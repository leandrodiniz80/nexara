from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.db.sync_session import SyncSessionLocal
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.auth.auth_repository import AuthRepository
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer

# `audit=PlatformAudit()` (Sprint 255): PlatformContainer's own `audit`
# param defaults to None, and every audit-logging call site in this
# codebase already guards with `if container.audit is not None`. Without
# constructing one here, the process-wide production container this
# dependency serves would have no audit trail at all — not just for the
# new admin-access logging this sprint adds, but for every other event
# (registration, login, plan upgrades, ...) that already calls
# `self.audit.log_event(...)` inside PlatformContainer whenever `audit` is
# configured. In-memory only (bounded to 10,000 events by PlatformAudit
# itself) — same "evolves to real persistence later" scope as everything
# else in this platform still backed by InMemoryStorage.
#
# Fase 1 (auth persistence): `auth_secret`/`auth_repository` are what turn
# on real Postgres persistence for users/organizations/sessions/usage
# (see PlatformAuth.__init__ and PlatformContainer._init_auth). Without
# `auth_secret=settings.SECRET_KEY.encode()`, PlatformAuth would keep
# generating a random HMAC secret on every process start (`os.urandom(32)`
# in PlatformAuth.__init__) — every session token signed before a restart
# or redeploy would fail verification afterward. `SECRET_KEY` is already
# a required setting for the whole platform, not a new secret to
# provision.
_container = PlatformContainer(
    bootstrap=PlatformBootstrap(),
    audit=PlatformAudit(),
    auth_secret=settings.SECRET_KEY.encode(),
    auth_repository=AuthRepository(SyncSessionLocal),
)
_bearer_scheme = HTTPBearer(auto_error=False)


def get_platform_container() -> PlatformContainer:
    """One PlatformContainer shared by the whole process. This is safe only because
    every route resolves its own session by token through `container.auth()`
    (which takes the token/email explicitly on every call) instead of touching
    `container.login()/current_user()/require_auth()`, whose `_current_token` is a
    single mutable pointer never safe to share across concurrent requests."""
    return _container


def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return credentials.credentials


def get_current_session(
    token: str = Depends(get_current_token),
    container: PlatformContainer = Depends(get_platform_container),
) -> dict:
    session = container.auth().get_session(token)

    if session is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return {**session, "token": token}


def get_optional_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    container: PlatformContainer = Depends(get_platform_container),
) -> dict | None:
    """Same lookup as `get_current_session`, but returns None instead of 401 when
    no (or an invalid) token is supplied — for routes that must stay usable
    anonymously (e.g. read-models) while still rate-limiting authenticated callers.
    """
    if credentials is None:
        return None

    session = container.auth().get_session(credentials.credentials)

    if session is None:
        return None

    return {**session, "token": credentials.credentials}
