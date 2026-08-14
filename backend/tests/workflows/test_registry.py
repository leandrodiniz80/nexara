import uuid

import pytest

from app.application.tasks.base.application_task import TaskType
from app.workflows.builders.workflow_builder import WorkflowBuilder
from app.workflows.exceptions.workflow_exceptions import (
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)
from app.workflows.registry.workflow_registry import WorkflowRegistry


def _workflow(**overrides):
    defaults = dict(
        name="Test Workflow",
        steps=[WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")],
        version=1,
    )
    defaults.update(overrides)
    return WorkflowBuilder.build_workflow(**defaults)


def test_register_and_get_active_round_trip():
    registry = WorkflowRegistry()
    workflow = _workflow()

    registry.register(workflow)

    assert registry.get_active("Test Workflow") is workflow


def test_get_active_for_unknown_name_raises():
    registry = WorkflowRegistry()

    with pytest.raises(WorkflowNotFoundError):
        registry.get_active("Does Not Exist")


def test_registering_a_new_version_becomes_active_by_default():
    registry = WorkflowRegistry()
    v1 = _workflow(version=1)
    v2 = _workflow(version=2)
    registry.register(v1)

    registry.register(v2)

    assert registry.get_active("Test Workflow") is v2


def test_register_without_activate_keeps_the_previous_version_active():
    registry = WorkflowRegistry()
    v1 = _workflow(version=1)
    v2 = _workflow(version=2)
    registry.register(v1)

    registry.register(v2, activate=False)

    assert registry.get_active("Test Workflow") is v1


def test_activate_version_switches_the_active_version():
    registry = WorkflowRegistry()
    v1 = _workflow(version=1)
    v2 = _workflow(version=2)
    registry.register(v1)
    registry.register(v2, activate=False)

    registry.activate_version("Test Workflow", 1)

    assert registry.get_active("Test Workflow") is v1


def test_get_version_for_unknown_version_raises():
    registry = WorkflowRegistry()
    registry.register(_workflow(version=1))

    with pytest.raises(WorkflowVersionNotFoundError):
        registry.get_version("Test Workflow", 99)


def test_list_workflows_returns_registered_names():
    registry = WorkflowRegistry()
    registry.register(_workflow(name="A"))
    registry.register(_workflow(name="B"))

    assert set(registry.list_workflows()) == {"A", "B"}


def test_list_versions_returns_every_registered_version():
    registry = WorkflowRegistry()
    v1 = _workflow(version=1)
    v2 = _workflow(version=2)
    registry.register(v1)
    registry.register(v2)

    versions = registry.list_versions("Test Workflow")

    assert {w.version for w in versions} == {1, 2}


def test_get_by_id_finds_any_registered_version():
    registry = WorkflowRegistry()
    workflow = _workflow()
    registry.register(workflow)

    assert registry.get_by_id(workflow.id) is workflow


def test_get_by_id_for_unknown_id_returns_none():
    registry = WorkflowRegistry()

    assert registry.get_by_id(uuid.uuid4()) is None
