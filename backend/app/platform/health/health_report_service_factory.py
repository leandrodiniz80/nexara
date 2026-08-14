from app.platform.health.health_executor_factory import build_default_health_executor
from app.platform.health.health_report_service import HealthReportService


def build_default_health_report_service() -> HealthReportService:
    """Composition root for this service. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_health_executor()`, and wires it into a
    HealthReportService — nothing else.
    """
    return HealthReportService(executor=build_default_health_executor())
