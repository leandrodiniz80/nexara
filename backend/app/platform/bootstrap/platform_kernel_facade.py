from typing import Any

from pydantic import BaseModel, ConfigDict

from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.bootstrap.platform_read_models import PlatformReadModels


class PlatformKernelFacade(BaseModel):
    """The platform's single official public facade of the Kernel — a
    frozen model holding exactly one collaborator. It never constructs
    anything itself and knows no concrete implementation of anything it
    resolves, nor any of the layers PlatformContainer itself sits on:
    every method delegates exclusively to `container`, with no additional
    logic of its own.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    container: PlatformContainer

    def resolve(self, name: str) -> Any:
        return self.container.resolve(name)

    def exists(self, name: str) -> bool:
        return self.container.exists(name)

    def list(self) -> list:
        return self.container.list()

    def health(self) -> Any:
        return self.container.health()

    def lifecycle(self) -> Any:
        return self.container.lifecycle()

    def services(self) -> list:
        return self.container.services_projection()

    def events(self) -> Any:
        return self.container.resolve("events")

    def capabilities(self) -> Any:
        return self.container.capabilities()

    def features(self) -> Any:
        return self.container.features()

    def catalog(self) -> Any:
        return self.container.catalog()

    def projections(self) -> dict[str, Any]:
        return self.container.projections()

    def service_names(self) -> tuple[str, ...]:
        return self.container.service_names()

    def service_map(self) -> dict[str, object]:
        return self.container.service_map()

    def services_projection(self) -> list:
        return self.container.services_projection()

    def read_models(self) -> PlatformReadModels:
        return self.container.read_models()

    def read_models_v1(self) -> dict:
        return self.container.read_models_v1()

    def read_models_version(self) -> str:
        return self.container.read_models_version()

    def read_models_v1_version(self) -> str:
        return self.container.read_models_v1_version()

    def read_models_v2(self) -> PlatformReadModels:
        return self.container.read_models_v2()

    def catalog_projection(self) -> Any:
        return self.container.catalog_projection()

    def service_names_projection(self) -> tuple[str, ...]:
        return self.container.service_names_projection()

    def auth(self) -> Any:
        return self.container.auth()

    def login(self, email: str, password: str) -> dict | None:
        return self.container.login(email, password)

    def current_user(self) -> dict | None:
        return self.container.current_user()

    def logout(self) -> None:
        return self.container.logout()

    def require_auth(self) -> dict:
        return self.container.require_auth()

    def current_user_email(self) -> str:
        return self.container.current_user_email()

    def execute_authenticated(self, fn, *args, **kwargs):
        return self.container.execute_authenticated(fn, *args, **kwargs)

    def current_user_role(self) -> str | None:
        return self.container.current_user_role()

    def require_role(self, role: str) -> None:
        return self.container.require_role(role)

    def execute_with_role(self, role: str, fn, *args, **kwargs):
        return self.container.execute_with_role(role, fn, *args, **kwargs)

    def execute_secure(self, fn, *args, role: str | None = None, **kwargs):
        return self.container.execute_secure(fn, *args, role=role, **kwargs)

    def current_user_permissions(self) -> list[str]:
        return self.container.current_user_permissions()

    def require_permission(self, permission: str) -> None:
        return self.container.require_permission(permission)

    def execute_with_permission(self, permission: str, fn, *args, **kwargs):
        return self.container.execute_with_permission(permission, fn, *args, **kwargs)

    def current_organization_id(self) -> str | None:
        return self.container.current_organization_id()

    def require_same_organization(self, resource_org_id: str) -> None:
        return self.container.require_same_organization(resource_org_id)

    def execute_in_organization(self, resource_org_id: str, fn, *args, **kwargs):
        return self.container.execute_in_organization(resource_org_id, fn, *args, **kwargs)

    def check_plan_limit(self, limit_key: str) -> None:
        return self.container.check_plan_limit(limit_key)

    def execute_with_limit(self, limit_key: str, fn, *args, **kwargs):
        return self.container.execute_with_limit(limit_key, fn, *args, **kwargs)

    def upgrade_plan(self, plan: str) -> None:
        return self.container.upgrade_plan(plan)

    def check_rate_limit(self) -> None:
        return self.container.check_rate_limit()

    def execute_with_rate_limit(self, fn, *args, **kwargs):
        return self.container.execute_with_rate_limit(fn, *args, **kwargs)

    def set_tenant(self, organization_id: str) -> None:
        return self.container.set_tenant(organization_id)

    def get_tenant_id(self) -> str:
        return self.container.get_tenant_id()

    def ensure_same_tenant(self, org_id: str) -> None:
        return self.container.ensure_same_tenant(org_id)
