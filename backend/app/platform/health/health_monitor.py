from pydantic import BaseModel, ConfigDict

from app.platform.health.health_report import HealthReport
from app.platform.health.platform_health import PlatformHealth


class HealthMonitor(BaseModel):
    """The platform's official layer for monitoring platform health — a
    frozen model holding exactly one collaborator. `monitor()` delegates
    exclusively to `platform_health.health()` and returns exactly the
    HealthReport it produced, fresh on every call. No additional logic,
    no interpretation, no exception handling.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    platform_health: PlatformHealth

    def monitor(self) -> HealthReport:
        return self.platform_health.health()
