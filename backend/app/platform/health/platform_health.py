from pydantic import BaseModel, ConfigDict

from app.platform.health.health_report import HealthReport
from app.platform.health.health_report_service import HealthReportService


class PlatformHealth(BaseModel):
    """The platform's official public facade for Health — a frozen model
    holding exactly one collaborator. `health()` delegates exclusively to
    `health_report_service.build()` and returns exactly the HealthReport
    it produced, fresh on every call. No additional logic, no
    interpretation, no exception handling.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    health_report_service: HealthReportService

    def health(self) -> HealthReport:
        return self.health_report_service.build()
