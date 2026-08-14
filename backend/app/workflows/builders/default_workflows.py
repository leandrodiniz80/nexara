from app.application.tasks.base.application_task import TaskType
from app.workflows.builders.workflow_builder import WorkflowBuilder
from app.workflows.models.workflow import Workflow


def build_prospecting_workflow() -> Workflow:
    """ResearchTask -> QualificationTask -> CopyTask."""
    return WorkflowBuilder.build_workflow(
        name="Prospecting Workflow",
        description="Find companies, qualify them, and generate the first outreach copy.",
        steps=[
            WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research"),
            WorkflowBuilder.build_step(
                order=2, task_type=TaskType.QUALIFICATION, name="qualification"
            ),
            WorkflowBuilder.build_step(order=3, task_type=TaskType.COPY, name="copy_generation"),
        ],
    )


def build_proposal_workflow() -> Workflow:
    """QualificationTask -> ProposalTask."""
    return WorkflowBuilder.build_workflow(
        name="Proposal Workflow",
        description="Re-qualify a prospect and generate a proposal asset for it.",
        steps=[
            WorkflowBuilder.build_step(
                order=1, task_type=TaskType.QUALIFICATION, name="qualification"
            ),
            WorkflowBuilder.build_step(
                order=2, task_type=TaskType.PROPOSAL, name="proposal_generation"
            ),
        ],
    )


def build_followup_workflow() -> Workflow:
    """FollowupTask alone."""
    return WorkflowBuilder.build_workflow(
        name="Follow-up Workflow",
        description="Generate a follow-up asset for a prospect already contacted.",
        steps=[
            WorkflowBuilder.build_step(order=1, task_type=TaskType.FOLLOWUP, name="followup"),
        ],
    )


def build_default_workflows() -> list[Workflow]:
    return [
        build_prospecting_workflow(),
        build_proposal_workflow(),
        build_followup_workflow(),
    ]
