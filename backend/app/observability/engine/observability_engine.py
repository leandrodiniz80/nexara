import uuid
from datetime import datetime
from typing import Any

from app.observability.audit.audit_service import AuditService
from app.observability.metrics.metrics_service import MetricsService
from app.observability.models.audit_entry import AuditEntry
from app.observability.models.execution_statistics import ExecutionStatistics
from app.observability.models.execution_step import ExecutionStatus
from app.observability.models.execution_trace import ExecutionTrace
from app.observability.models.performance_metric import PerformanceMetric
from app.observability.repositories.observability_repository import ObservabilityRepository
from app.observability.schemas.audit_timeline import AuditTimeline
from app.observability.tracing.trace_builder import TraceBuilder
from app.observability.tracing.trace_context import TraceContext
from app.observability.tracing.trace_factory import TraceFactory


class ObservabilityEngine:
    """The single facade this module exposes. Takes no decisions of its own — every
    method here either delegates to a deterministic builder/calculator or persists
    through ObservabilityRepository. Nothing in the rest of the platform calls this
    yet (Sprint 16 only builds the infrastructure); wiring it into
    Missions/Prospects/Tasks/Jobs is explicitly left for a future sprint.
    """

    def __init__(
        self,
        repository: ObservabilityRepository,
        audit_service: AuditService,
        metrics_service: MetricsService,
        trace_builder: TraceBuilder | None = None,
        trace_factory: TraceFactory | None = None,
    ) -> None:
        self.repository = repository
        self.audit_service = audit_service
        self.metrics_service = metrics_service
        self.trace_builder = trace_builder or TraceBuilder()
        self.trace_factory = trace_factory or TraceFactory()

    def start_trace(self, context: TraceContext, execution_type: str) -> ExecutionTrace:
        trace = self.trace_factory.create(context, execution_type)
        return self.repository.save_trace(trace)

    def finish_trace(
        self, trace: ExecutionTrace, *, status: ExecutionStatus
    ) -> ExecutionTrace:
        trace = self.trace_builder.finish(trace, status=status)
        return self.repository.save_trace(trace)

    def register_step(
        self,
        trace: ExecutionTrace,
        *,
        step_name: str,
        component: str,
        started_at: datetime,
        finished_at: datetime,
        status: ExecutionStatus,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> ExecutionTrace:
        step = self.trace_builder.build_step(
            step_name=step_name,
            component=component,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            warnings=warnings,
            errors=errors,
        )
        trace = self.trace_builder.append_step(trace, step)
        return self.repository.save_trace(trace)

    def register_metric(
        self,
        *,
        component: str,
        operation: str,
        execution_time: float,
        success: bool,
        memory_usage: float | None = None,
        cpu_usage: float | None = None,
    ) -> PerformanceMetric:
        return self.metrics_service.record(
            component=component,
            operation=operation,
            execution_time=execution_time,
            success=success,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
        )

    def register_audit(
        self,
        *,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        performed_by: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.audit_service.record(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            performed_by=performed_by,
            metadata=metadata,
        )

    def build_statistics(
        self, *, component: str | None = None, operation: str | None = None
    ) -> ExecutionStatistics:
        return self.metrics_service.build_statistics(component=component, operation=operation)

    def build_timeline(self, entity_type: str, entity_id: uuid.UUID) -> AuditTimeline:
        return self.audit_service.build_timeline(entity_type, entity_id)
