import uuid

from app.observability.models.audit_entry import AuditEntry
from app.observability.models.execution_trace import ExecutionTrace
from app.observability.models.performance_metric import PerformanceMetric


class ObservabilityRepository:
    """In-memory store of every ExecutionTrace/AuditEntry/PerformanceMetric — no
    database, same reasoning as every other in-memory repository in this codebase
    (ResearchResultRepository, JobRepository, SalesIntelligenceRepository): no
    migration was requested for this module, and swapping in a persisted
    implementation later can happen behind this same interface.
    """

    def __init__(self) -> None:
        self._traces: dict[uuid.UUID, ExecutionTrace] = {}
        self._audit_entries: list[AuditEntry] = []
        self._metrics: list[PerformanceMetric] = []

    # --- traces --------------------------------------------------------------

    def save_trace(self, trace: ExecutionTrace) -> ExecutionTrace:
        self._traces[trace.trace_id] = trace
        return trace

    def get_trace(self, trace_id: uuid.UUID) -> ExecutionTrace | None:
        return self._traces.get(trace_id)

    def list_traces(
        self,
        *,
        execution_type: str | None = None,
        mission_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
    ) -> list[ExecutionTrace]:
        traces = list(self._traces.values())
        if execution_type is not None:
            traces = [t for t in traces if t.execution_type == execution_type]
        if mission_id is not None:
            traces = [t for t in traces if t.mission_id == mission_id]
        if job_id is not None:
            traces = [t for t in traces if t.job_id == job_id]
        return traces

    # --- audit entries ---------------------------------------------------------

    def save_audit_entry(self, entry: AuditEntry) -> AuditEntry:
        self._audit_entries.append(entry)
        return entry

    def list_audit_entries_by_entity(
        self, entity_type: str, entity_id: uuid.UUID
    ) -> list[AuditEntry]:
        return [
            entry
            for entry in self._audit_entries
            if entry.entity_type == entity_type and entry.entity_id == entity_id
        ]

    def list_all_audit_entries(self) -> list[AuditEntry]:
        return list(self._audit_entries)

    # --- performance metrics ----------------------------------------------------

    def save_metric(self, metric: PerformanceMetric) -> PerformanceMetric:
        self._metrics.append(metric)
        return metric

    def list_metrics(
        self, *, component: str | None = None, operation: str | None = None
    ) -> list[PerformanceMetric]:
        metrics = list(self._metrics)
        if component is not None:
            metrics = [m for m in metrics if m.component == component]
        if operation is not None:
            metrics = [m for m in metrics if m.operation == operation]
        return metrics
