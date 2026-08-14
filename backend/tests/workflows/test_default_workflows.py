import uuid
from datetime import datetime, timezone

from app.application.tasks.base.application_task import TaskType
from app.application.tasks.context.task_context import TaskContext
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.schemas.prospecting.company import CompanyRead
from app.workflows.builders.default_workflows import (
    build_default_workflows,
    build_followup_workflow,
    build_proposal_workflow,
    build_prospecting_workflow,
)
from app.workflows.models.enums import WorkflowStatus
from app.workflows.schemas.workflow_request import WorkflowRequest
from app.workflows.schemas.workflow_summary import WorkflowSummary
from app.workflows.services.workflow_engine_factory import build_default_workflow_engine


def test_prospecting_workflow_sequence_is_research_qualification_copy():
    workflow = build_prospecting_workflow()

    task_types = [step.task_type for step in sorted(workflow.steps, key=lambda s: s.order)]

    assert workflow.name == "Prospecting Workflow"
    assert task_types == [TaskType.RESEARCH, TaskType.QUALIFICATION, TaskType.COPY]


def test_proposal_workflow_sequence_is_qualification_then_proposal():
    workflow = build_proposal_workflow()

    task_types = [step.task_type for step in sorted(workflow.steps, key=lambda s: s.order)]

    assert workflow.name == "Proposal Workflow"
    assert task_types == [TaskType.QUALIFICATION, TaskType.PROPOSAL]


def test_followup_workflow_is_a_single_step():
    workflow = build_followup_workflow()

    assert workflow.name == "Follow-up Workflow"
    assert len(workflow.steps) == 1
    assert workflow.steps[0].task_type == TaskType.FOLLOWUP


def test_build_default_workflows_returns_all_three():
    workflows = build_default_workflows()

    assert {w.name for w in workflows} == {
        "Prospecting Workflow",
        "Proposal Workflow",
        "Follow-up Workflow",
    }


def test_default_workflows_are_deterministic_across_calls():
    first = build_default_workflows()
    second = build_default_workflows()

    assert [w.name for w in first] == [w.name for w in second]
    assert [[s.task_type for s in w.steps] for w in first] == [
        [s.task_type for s in w.steps] for w in second
    ]


def test_workflow_summary_from_workflow_reflects_the_sequence():
    workflow = build_prospecting_workflow()

    summary = WorkflowSummary.from_workflow(workflow)

    assert summary.name == "Prospecting Workflow"
    assert summary.step_count == 3
    assert summary.task_types == [TaskType.RESEARCH, TaskType.QUALIFICATION, TaskType.COPY]


def test_build_default_workflow_engine_registers_all_three_by_default():
    engine = build_default_workflow_engine()

    assert set(engine.registry.list_workflows()) == {
        "Prospecting Workflow",
        "Proposal Workflow",
        "Follow-up Workflow",
    }


def test_build_default_workflow_engine_wires_every_task_type():
    engine = build_default_workflow_engine()

    assert set(engine.tasks.keys()) == set(TaskType)


def _company() -> CompanyRead:
    return CompanyRead(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        legal_name="Agência XYZ Ltda",
        trade_name="Agência XYZ",
        cnpj="12345678000199",
        segment="Publicidade",
        city="Goiânia",
        state="GO",
    )


async def test_prospecting_workflow_runs_end_to_end_with_real_tasks():
    """Uses the real ResearchTask/QualificationTask/CopyTask (via TaskFactory),
    never a hand-rolled fake — only the Providers underneath them are Mocks, the
    same "swap the provider, not the task" pattern every prior sprint established."""
    engine = build_default_workflow_engine()
    context = TaskContext(
        mission_id=uuid.uuid4(),
        prospect_id=uuid.uuid4(),
        variables={
            "strategy": "city",
            "query": {"city": "Goiânia"},
            "profile": CommercialProfile(segment="retail", company_size="small"),
            "company": _company(),
            "asset_type": "email",
        },
    )

    response = await engine.execute(
        WorkflowRequest(workflow_name="Prospecting Workflow", context=context)
    )

    assert response.result.execution.status in {WorkflowStatus.COMPLETED, WorkflowStatus.PAUSED}
    assert response.result.execution.completed_steps
