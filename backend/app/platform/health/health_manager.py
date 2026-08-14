from pydantic import BaseModel, ConfigDict

from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry


class HealthManager(BaseModel):
    """An intermediate layer over HealthCheckRegistry — a frozen model
    holding exactly one collaborator. It never runs a check, never caches
    or memoizes anything itself: every method is a direct, single-line
    delegation to `registry`, nothing more.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    registry: HealthCheckRegistry

    def check(self, name: str) -> HealthCheck | None:
        return self.registry.find(name)

    def exists(self, name: str) -> bool:
        return self.registry.exists(name)

    def checks(self) -> list[HealthCheck]:
        return self.registry.list()
