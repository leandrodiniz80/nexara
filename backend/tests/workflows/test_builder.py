import pytest

from app.application.tasks.base.application_task import TaskType
from app.workflows.builders.workflow_builder import WorkflowBuilder


def test_build_step_applies_defaults():
    step = WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")

    assert step.required is True
    assert step.continue_on_error is False
    assert step.timeout is None
    assert step.metadata == {}


def test_build_step_is_frozen():
    step = WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")

    with pytest.raises(Exception):
        step.order = 2


def test_build_workflow_orders_are_preserved_as_given():
    steps = [
        WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research"),
        WorkflowBuilder.build_step(order=2, task_type=TaskType.QUALIFICATION, name="qualify"),
    ]

    workflow = WorkflowBuilder.build_workflow(name="Test Workflow", steps=steps)

    assert [step.order for step in workflow.steps] == [1, 2]
    assert workflow.version == 1
    assert workflow.is_active is True


def test_build_workflow_is_frozen():
    workflow = WorkflowBuilder.build_workflow(name="Test Workflow", steps=[])

    with pytest.raises(Exception):
        workflow.name = "Renamed"


def test_builder_is_deterministic_given_the_same_inputs():
    steps = [WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")]

    first = WorkflowBuilder.build_workflow(name="Test Workflow", steps=steps, version=1)
    second = WorkflowBuilder.build_workflow(name="Test Workflow", steps=steps, version=1)

    assert first.name == second.name
    assert first.steps == second.steps
    assert first.version == second.version
    # only identity (id) is allowed to differ between two builds
    assert first.id != second.id
