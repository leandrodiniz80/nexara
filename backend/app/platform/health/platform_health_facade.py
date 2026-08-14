from pydantic import BaseModel, ConfigDict

from app.platform.health.health_coordinator import HealthCoordinator
from app.platform.health.health_report import HealthReport


class PlatformHealthFacade(BaseModel):
    """The platform's official public entry point for health queries — a
    frozen model holding exactly one collaborator. `health()` delegates
    exclusively to `health_coordinator.coordinate()` and returns exactly
    the HealthReport it produced, fresh on every call. No additional
    logic, no interpretation, no exception handling.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    health_coordinator: HealthCoordinator

    def health(self) -> HealthReport:
        return self.health_coordinator.coordinate()
