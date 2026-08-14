import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.observability.exceptions.observability_exceptions import InvalidTraceTransitionError
from app.observability.models.execution_step import ExecutionStatus
from app.observability.schemas.trace_summary import TraceSummary
from app.observability.tracing.trace_builder import TraceBuilder
from app.observability.tracing.trace_context import TraceContext
from app.observability.tracing.trace_factory import TraceFactory


def test_trace_factory_creates_a_running_trace_from_context():
    context = TraceContext(mission_id=uuid.uuid4(), request_id="req-1")

    trace = TraceFactory.create(context, "mission_creation")

    assert trace.status == ExecutionStatus.RUNNING
    assert trace.execution_type == "mission_creation"
    assert trace.mission_id == context.mission_id
    assert trace.request_id == "req-1"
    assert trace.finished_at is None
    assert trace.steps == []


def test_trace_factory_is_deterministic_given_the_same_inputs_except_identity():
    context = TraceContext(mission_id=uuid.uuid4())

    first = TraceFactory.create(context, "mission_creation")
    second = TraceFactory.create(context, "mission_creation")

    assert first.trace_id != second.trace_id
    assert first.mission_id == second.mission_id
    assert first.execution_type == second.execution_type


def test_trace_builder_build_step_computes_duration():
    started_at = datetime.now(timezone.utc)
    finished_at = started_at + timedelta(seconds=2.5)

    step = TraceBuilder.build_step(
        step_name="search_companies",
        component="LeadDiscoveryPipeline",
        started_at=started_at,
        finished_at=finished_at,
        status=ExecutionStatus.SUCCESS,
    )

    assert step.duration == pytest.approx(2.5)
    assert step.warnings == []
    assert step.errors == []


def test_trace_builder_append_step_adds_to_the_trace():
    trace = TraceFactory.create(TraceContext(), "mission_creation")
    step = TraceBuilder.build_step(
        step_name="validate",
        component="MissionEngine",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        status=ExecutionStatus.SUCCESS,
    )

    trace = TraceBuilder.append_step(trace, step)

    assert len(trace.steps) == 1
    assert trace.steps[0] is step


def test_append_step_on_a_finished_trace_raises():
    trace = TraceFactory.create(TraceContext(), "mission_creation")
    trace = TraceBuilder.finish(trace, status=ExecutionStatus.SUCCESS)
    step = TraceBuilder.build_step(
        step_name="late",
        component="X",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        status=ExecutionStatus.SUCCESS,
    )

    with pytest.raises(InvalidTraceTransitionError):
        TraceBuilder.append_step(trace, step)


def test_trace_builder_finish_stamps_status_and_duration():
    trace = TraceFactory.create(TraceContext(), "mission_creation")

    finished = TraceBuilder.finish(trace, status=ExecutionStatus.SUCCESS)

    assert finished.status == ExecutionStatus.SUCCESS
    assert finished.finished_at is not None
    assert finished.duration is not None
    assert finished.duration >= 0


def test_finishing_an_already_finished_trace_raises():
    trace = TraceFactory.create(TraceContext(), "mission_creation")
    trace = TraceBuilder.finish(trace, status=ExecutionStatus.SUCCESS)

    with pytest.raises(InvalidTraceTransitionError):
        TraceBuilder.finish(trace, status=ExecutionStatus.FAILED)


def test_finishing_with_running_status_raises():
    trace = TraceFactory.create(TraceContext(), "mission_creation")

    with pytest.raises(InvalidTraceTransitionError):
        TraceBuilder.finish(trace, status=ExecutionStatus.RUNNING)


def test_trace_summary_from_trace_counts_steps_warnings_and_errors():
    trace = TraceFactory.create(TraceContext(), "mission_creation")
    ok_step = TraceBuilder.build_step(
        step_name="a",
        component="X",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        status=ExecutionStatus.SUCCESS,
    )
    failed_step = TraceBuilder.build_step(
        step_name="b",
        component="Y",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        status=ExecutionStatus.FAILED,
        warnings=["slow"],
        errors=["boom"],
    )
    trace = TraceBuilder.append_step(trace, ok_step)
    trace = TraceBuilder.append_step(trace, failed_step)
    trace = TraceBuilder.finish(trace, status=ExecutionStatus.FAILED)

    summary = TraceSummary.from_trace(trace)

    assert summary.trace_id == trace.trace_id
    assert summary.status == ExecutionStatus.FAILED
    assert summary.step_count == 2
    assert summary.error_count == 1
    assert summary.warning_count == 1
