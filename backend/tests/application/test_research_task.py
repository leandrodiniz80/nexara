import uuid

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import (
    TaskExecutionError,
    TaskValidationError,
)
from app.application.tasks.research_task import ResearchTask
from app.research.pipeline.factory import build_default_lead_discovery_pipeline


def test_validate_requires_mission_id():
    task = ResearchTask(build_default_lead_discovery_pipeline())

    with pytest.raises(TaskValidationError):
        task.validate(TaskContext(variables={"strategy": "city"}))


def test_validate_requires_strategy():
    task = ResearchTask(build_default_lead_discovery_pipeline())

    with pytest.raises(TaskValidationError):
        task.validate(TaskContext(mission_id=uuid.uuid4(), variables={}))


def test_validate_rejects_unknown_strategy():
    task = ResearchTask(build_default_lead_discovery_pipeline())

    context = TaskContext(mission_id=uuid.uuid4(), variables={"strategy": "carrier_pigeon"})
    with pytest.raises(TaskValidationError):
        task.validate(context)


async def test_execute_runs_the_real_lead_discovery_pipeline():
    """Uses the real LeadDiscoveryPipeline (via its own composition root), never a
    hand-rolled fake pipeline — only the provider underneath it is a Mock."""
    task = ResearchTask(build_default_lead_discovery_pipeline())
    context = TaskContext(
        mission_id=uuid.uuid4(),
        variables={"strategy": "city", "query": {"city": "Goiânia"}},
    )

    output = await task.execute(context)

    assert output["errors"] == []
    assert output["result"]["total_found"] > 0
    assert "search_companies" in output["steps"]


async def test_execute_raises_task_execution_error_when_pipeline_reports_errors():
    task = ResearchTask(build_default_lead_discovery_pipeline())
    context = TaskContext(
        mission_id=uuid.uuid4(),
        variables={"strategy": "city", "query": {}},
    )

    with pytest.raises(TaskExecutionError):
        await task.execute(context)


async def test_rollback_is_a_documented_no_op():
    task = ResearchTask(build_default_lead_discovery_pipeline())
    await task.rollback(TaskContext(mission_id=uuid.uuid4()))
