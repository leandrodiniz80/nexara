from pydantic import BaseModel, ConfigDict

from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_report import HealthReport
from app.platform.health.health_report_factory import build_health_report


class HealthReportService(BaseModel):
    """The platform's official layer for turning HealthExecutor's raw
    results into the official HealthReport contract — a frozen model
    holding exactly one collaborator. `build()` runs `executor.run()`,
    feeds the results into `build_health_report()`, and returns exactly
    the HealthReport it produced. No additional logic, no interpretation,
    no exception handling.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    executor: HealthExecutor

    def build(self) -> HealthReport:
        results = self.executor.run()
        return build_health_report(results)
