from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, PrivateAttr, model_validator

from app.platform.audit.platform_audit import PlatformAudit
from app.platform.auth.platform_auth import PlatformAuth
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_read_models import PlatformReadModels
from app.platform.bootstrap.platform_read_models_version import READ_MODELS_VERSION
from app.platform.cache.platform_cache import PlatformCache
from app.platform.logging.platform_logger import PlatformLogger
from app.platform.metrics.platform_metrics import PlatformMetrics
from app.platform.storage.platform_storage import PlatformStorage
from app.platform.tenant.tenant_context import TenantContext


class PlatformContainer(BaseModel):
    """The platform's single official public facade for resolving
    published services — a frozen model holding exactly one collaborator.
    It never constructs anything itself and knows no concrete
    implementation of anything it resolves: every method delegates
    exclusively to `bootstrap.resolver()`, with no additional logic of
    its own. `health()` is a plain ergonomic shortcut for
    `resolve("health")` — it changes no internal resolution mechanism.
    `catalog()` is the one exception: it delegates straight to
    `bootstrap.catalog()`, never through `resolve()`, since the catalog
    is a derived read-only view and is never registered as a
    resolvable service.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    bootstrap: PlatformBootstrap
    storage: PlatformStorage | None = None
    cache: PlatformCache | None = None
    audit: PlatformAudit | None = None
    metrics: PlatformMetrics | None = None
    logger: PlatformLogger | None = None

    _v2_registry: dict = PrivateAttr(default_factory=dict)
    _v2_counter: list = PrivateAttr(default_factory=lambda: [0])
    _v2_meta: dict = PrivateAttr(default_factory=dict)

    _auth: PlatformAuth | None = PrivateAttr(default=None)
    _current_token: str | None = PrivateAttr(default=None)

    # Same single-actor caveat as `_current_token`: safe for CLI/tests/scripts
    # that own one Container exclusively, never for the shared per-process
    # singleton under concurrent HTTP traffic. The API layer must never call
    # `set_tenant`/`get_tenant_id` — see `app/api/middleware/tenant.py`, which
    # resolves tenant per-request via `request.state` instead.
    _tenant_context: TenantContext | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _init_auth(self) -> "PlatformContainer":
        self._auth = PlatformAuth(
            storage=self.storage,
            cache=self.cache,
            audit=self.audit,
            metrics=self.metrics,
            logger=self.logger,
        )

        return self

    def resolve(self, name: str) -> Any:
        return self.bootstrap.resolver().resolve(name)

    def exists(self, name: str) -> bool:
        return self.bootstrap.resolver().exists(name)

    def list(self) -> list:
        return self.bootstrap.resolver().list()

    def health(self) -> Any:
        return self.resolve("health")

    def events(self) -> Any:
        return self.resolve("events")

    def lifecycle(self) -> Any:
        return self.resolve("lifecycle")

    def capabilities(self) -> Any:
        return self.resolve("capabilities")

    def features(self) -> Any:
        return self.resolve("features")

    def catalog(self) -> Any:
        return self.bootstrap.catalog()

    def projections(self) -> dict[str, Any]:
        return self._build_projections()

    def _build_projections(self) -> dict[str, Any]:
        return {
            "catalog": self.catalog(),
            "services": self.list(),
            "service_names": tuple(descriptor.name for descriptor in self.list()),
            "service_map": {descriptor.name: descriptor.instance for descriptor in self.list()},
        }

    def service_names(self) -> tuple[str, ...]:
        return self.service_names_projection()

    def service_map(self) -> dict[str, object]:
        return self.service_map_projection()

    def services_projection(self) -> list:
        return self.list()

    def read_models(self) -> PlatformReadModels:
        return self.projections()

    def read_models_validated(self) -> PlatformReadModels:
        data = self.read_models()

        from app.platform.bootstrap.platform_read_models_validator import validate_read_models

        validate_read_models(data)

        return data

    def read_models_version(self) -> str:
        return READ_MODELS_VERSION

    def read_models_v1(self) -> PlatformReadModels:
        from app.platform.bootstrap.platform_read_models_compat import get_read_models_v1

        data = self.read_models()

        return get_read_models_v1(data)

    def read_models_v1_version(self) -> str:
        return self.read_models_version()

    def read_models_v2(self) -> PlatformReadModels:
        from app.platform.bootstrap.platform_read_models_compat import get_read_models_v2

        return get_read_models_v2(
            self.read_models(),
            self._v2_registry,
            self._v2_counter,
            self._v2_meta,
        )

    def _is_v2(self, data: PlatformReadModels) -> bool:
        from app.platform.bootstrap.platform_read_models_compat import is_v2

        return is_v2(data, self._v2_registry)

    def _get_v2_meta(self, data: PlatformReadModels) -> dict | None:
        from app.platform.bootstrap.platform_read_models_compat import get_v2_meta

        return get_v2_meta(data, self._v2_meta)

    def compare_read_models_versions(self) -> dict:
        from app.platform.bootstrap.platform_read_models_compat import compare_v1_v2

        v1 = self.read_models_v1()
        v2 = self.read_models_v2()

        return compare_v1_v2(v1, v2)

    def auth(self) -> PlatformAuth:
        return self._auth

    def login(self, email: str, password: str) -> dict | None:
        session = self._auth.login(email, password)

        if session is not None:
            self._current_token = session["token"]

        return session

    def current_user(self) -> dict | None:
        if self._current_token is None:
            return None

        return self._auth.get_session(self._current_token)

    def logout(self) -> None:
        if self._current_token is not None:
            self._auth.logout(self._current_token)
            self._current_token = None

    def require_auth(self) -> dict:
        user = self.current_user()

        if self.audit is not None:
            self.audit.log_event(
                "auth_checked",
                user["email"] if user is not None else None,
                user.get("organization_id") if user is not None else None,
                {"result": "granted" if user is not None else "denied"},
            )

        if user is None:
            raise PermissionError("Not authenticated")

        return user

    def current_user_email(self) -> str:
        user = self.require_auth()

        return user["email"]

    def execute_authenticated(self, fn, *args, **kwargs):
        self.require_auth()

        return fn(*args, **kwargs)

    def current_user_role(self) -> str | None:
        user = self.require_auth()

        return self._auth.get_user_role(user["email"])

    def require_role(self, role: str) -> None:
        current_role = self.current_user_role()
        granted = current_role == role

        if self.audit is not None:
            user = self.current_user()
            self.audit.log_event(
                "role_checked",
                user["email"] if user is not None else None,
                user.get("organization_id") if user is not None else None,
                {"required_role": role, "result": "granted" if granted else "denied"},
            )

        if not granted:
            raise PermissionError("Acesso negado")

    def execute_with_role(self, role: str, fn, *args, **kwargs):
        self.require_role(role)

        return fn(*args, **kwargs)

    def execute_secure(self, fn, *args, role: str | None = None, **kwargs):
        if role is not None:
            self.require_role(role)
        else:
            self.require_auth()

        return fn(*args, **kwargs)

    def current_user_permissions(self) -> list[str]:
        user = self.require_auth()

        return self._auth.get_user_permissions(user["email"])

    def require_permission(self, permission: str) -> None:
        permissions = self.current_user_permissions()
        granted = permission in permissions

        if self.audit is not None:
            user = self.current_user()
            self.audit.log_event(
                "permission_checked",
                user["email"] if user is not None else None,
                user.get("organization_id") if user is not None else None,
                {"required_permission": permission, "result": "granted" if granted else "denied"},
            )

        if not granted:
            raise PermissionError(f"Permission '{permission}' requerida")

    def execute_with_permission(self, permission: str, fn, *args, **kwargs):
        self.require_permission(permission)

        return fn(*args, **kwargs)

    def current_organization_id(self) -> str | None:
        user = self.require_auth()

        return self._auth.get_user_organization(user["email"])

    def require_same_organization(self, resource_org_id: str) -> None:
        current_org = self.current_organization_id()

        if current_org != resource_org_id:
            raise PermissionError("Access denied: different organization")

    def execute_in_organization(self, resource_org_id: str, fn, *args, **kwargs):
        self.require_same_organization(resource_org_id)

        return fn(*args, **kwargs)

    def set_tenant(self, organization_id: str) -> None:
        self._tenant_context = TenantContext(organization_id)

    def get_tenant_id(self) -> str:
        self.require_auth()

        if self._tenant_context is not None:
            return self._tenant_context.organization_id

        return self.current_organization_id()

    def ensure_same_tenant(self, org_id: str) -> None:
        if self.get_tenant_id() != org_id:
            raise PermissionError("Access denied: different tenant")

    def check_plan_limit(self, limit_key: str) -> None:
        org_id = self.current_organization_id()

        self._auth.check_limit(org_id, limit_key)

    def execute_with_limit(self, limit_key: str, fn, *args, **kwargs):
        org_id = self.current_organization_id()

        self._auth.check_limit(org_id, limit_key)
        result = fn(*args, **kwargs)
        self._auth.increment_usage(org_id, limit_key)

        return result

    def check_rate_limit(self) -> None:
        user = self.require_auth()

        self._auth.check_rate_limit(user["email"])

    def execute_with_rate_limit(self, fn, *args, **kwargs):
        self.check_rate_limit()

        return fn(*args, **kwargs)

    def upgrade_plan(self, plan: str) -> None:
        user = self.require_auth()
        org_id = self._auth.get_user_organization(user["email"])
        org_role = self._auth.get_user_organization_role(user["email"])

        if org_role != "owner":
            raise PermissionError("Only the organization owner can change the plan")

        self._auth.set_organization_plan(org_id, plan)

        if self.audit is not None:
            self.audit.log_event("plan_upgraded", user["email"], org_id, {"plan": plan})

    def catalog_projection(self) -> Any:
        return self.catalog()

    def service_names_projection(self) -> tuple[str, ...]:
        return tuple(descriptor.name for descriptor in self.list())

    def service_map_projection(self) -> dict[str, object]:
        return {descriptor.name: descriptor.instance for descriptor in self.list()}
