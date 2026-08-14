from pydantic import BaseModel, ConfigDict

from app.platform.health.health_monitor import HealthMonitor
from app.platform.health.health_report import HealthReport


class HealthCoordinator(BaseModel):
    """The platform's official coordination layer for the Health
    infrastructure — a frozen model holding exactly one collaborator.
    `coordinate()` delegates exclusively to `health_monitor.monitor()` and
    returns exactly the HealthReport it produced, fresh on every call. No
    additional logic, no interpretation, no exception handling.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    health_monitor: HealthMonitor

    def coordinate(self) -> HealthReport:
        return self.health_monitor.monitor()
