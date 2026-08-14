import uuid
from datetime import datetime, timezone

import pytest

from app.observability.exceptions.observability_exceptions import InvalidTraceTransitionError
from app.observability.models.execution_step import ExecutionStatus
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)
from app.observability.tracing.trace_context import TraceContext


def test_start_trace_persists_a_running_trace():
    engine = build_default_observability_engine()
    context = TraceContext(mission_id=uuid.uuid4())

    trace = engine.start_trace(context, "mission_creation")

    assert trace.status == ExecutionStatus.RUNNING
    assert engine.repository.get_trace(trace.trace_id) is trace


def test_full_trace_lifecycle_with_steps():
    engine = build_default_observability_engine()
    trace = engine.start_trace(TraceContext(mission_id=uuid.uuid4()), "mission_creation")
    now = datetime.now(timezone.utc)

    trace = engine.register_step(
        trace,
        step_name="research",
        component="ResearchTask",
        started_at=now,
        finished_at=now,
        status=ExecutionStatus.SUCCESS,
    )
    trace = engine.register_step(
        trace,
        step_name="qualification",
        component="QualificationTask",
        started_at=now,
        finished_at=now,
        status=ExecutionStatus.SUCCESS,
    )
    trace = engine.finish_trace(trace, status=ExecutionStatus.SUCCESS)

    assert len(trace.steps) == 2
    assert trace.status == ExecutionStatus.SUCCESS
    stored = engine.repository.get_trace(trace.trace_id)
    assert len(stored.steps) == 2


def test_register_step_after_finish_raises():
    engine = build_default_observability_engine()
    trace = engine.start_trace(TraceContext(), "mission_creation")
    trace = engine.finish_trace(trace, status=ExecutionStatus.SUCCESS)
    now = datetime.now(timezone.utc)

    with pytest.raises(InvalidTraceTransitionError):
        engine.register_step(
            trace,
            step_name="late",
            component="X",
            started_at=now,
            finished_at=now,
            status=ExecutionStatus.SUCCESS,
        )


def test_register_metric_and_build_statistics():
    engine = build_default_observability_engine()

    engine.register_metric(
        component="CopyAgent", operation="generate", execution_time=1.0, success=True
    )
    engine.register_metric(
        component="CopyAgent", operation="generate", execution_time=3.0, success=False
    )

    statistics = engine.build_statistics(component="CopyAgent")

    assert statistics.total_executions == 2
    assert statistics.successful == 1
    assert statistics.failed == 1
    assert statistics.average_execution_time == 2.0


def test_register_audit_and_build_timeline():
    engine = build_default_observability_engine()
    mission_id = uuid.uuid4()

    engine.register_audit(entity_type="mission", entity_id=mission_id, action="created")
    engine.register_audit(entity_type="mission", entity_id=mission_id, action="paused")

    timeline = engine.build_timeline("mission", mission_id)

    assert [entry.action for entry in timeline.entries] == ["created", "paused"]


def test_engine_never_touches_any_existing_domain_module():
    import app.observability.engine.observability_engine as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()
    for forbidden in (
        "app.models",
        "app.repositories",
        "app.research",
        "app.sales_intelligence",
        "app.ai",
        "app.jobs",
        "app.application",
        "app.api",
        "app.outreach",
    ):
        assert forbidden not in source
