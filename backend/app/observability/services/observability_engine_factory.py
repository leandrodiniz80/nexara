from app.observability.audit.audit_service import AuditService
from app.observability.engine.observability_engine import ObservabilityEngine
from app.observability.metrics.metrics_service import MetricsService
from app.observability.repositories.observability_repository import ObservabilityRepository


def build_default_observability_engine(
    *, repository: ObservabilityRepository | None = None
) -> ObservabilityEngine:
    """Composition root for this module — the one place that wires
    ObservabilityRepository into AuditService/MetricsService and those into a ready
    ObservabilityEngine, same pattern as every other module's own factory.
    """
    repository = repository or ObservabilityRepository()
    return ObservabilityEngine(
        repository=repository,
        audit_service=AuditService(repository),
        metrics_service=MetricsService(repository),
    )
