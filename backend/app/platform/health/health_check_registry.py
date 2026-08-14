from pydantic import BaseModel, ConfigDict, Field

from app.platform.health.health_check import HealthCheck
from app.shared.registry.registry import Registry


class HealthCheckRegistry(BaseModel):
    """The platform's frozen registry of HealthChecks — pure lookup,
    nothing else: it never runs a check, never knows any concrete check's
    domain, and never mutates in place. Implemented exclusively by
    encapsulating a generic Registry[HealthCheck] — no reimplementation of
    register/register_many/find/exists/list.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    checks: tuple[HealthCheck, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[HealthCheck]:
        return Registry(items=self.checks, key=lambda check: check.name())

    def register(self, check: HealthCheck) -> "HealthCheckRegistry":
        return HealthCheckRegistry(checks=tuple(self._as_registry().register(check).list()))

    def register_many(self, checks: list[HealthCheck]) -> "HealthCheckRegistry":
        return HealthCheckRegistry(
            checks=tuple(self._as_registry().register_many(checks).list())
        )

    def find(self, name: str) -> HealthCheck | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def list(self) -> list[HealthCheck]:
        return self._as_registry().list()
