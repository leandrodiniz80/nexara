from typing import Any, ClassVar

import pytest

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.executors.task_executor import TaskExecutor
from app.decision.engine.decision_engine import DecisionEngine
from app.decision.registry.strategy_registry import StrategyRegistry
from app.decision.repositories.decision_repository import DecisionRepository
from app.decision.strategies.recommendation_strategy import RecommendationStrategy
from app.workflows.adapters.decision_adapter import (
    RealDecisionAdapter,
    WorkflowDecisionUnavailableError,
)
from app.workflows.builders.workflow_builder import WorkflowBuilder
from app.workflows.engine.workflow_engine import WorkflowEngine
from app.workflows.exceptions.workflow_exceptions import WorkflowNotFoundError
from app.workflows.registry.workflow_registry import WorkflowRegistry
from app.workflows.repositories.workflow_repository import WorkflowRepository
from app.workflows.schemas.workflow_request import WorkflowRequest


class _EchoTask(ApplicationTask):
    name: ClassVar[str] = "echo_task"

    def __init__(self, task_type: TaskType) -> None:
        self.task_type = task_type

    def validate(self, context: TaskContext) -> None:
        pass

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        return {}

    async def rollback(self, context: TaskContext) -> None:
        pass


def _workflow(name: str):
    return WorkflowBuilder.build_workflow(
        name=name,
        steps=[WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")],
    )


def _engine(*, decision_adapter=None) -> WorkflowEngine:
    registry = WorkflowRegistry()
    registry.register(_workflow("Workflow A"))
    registry.register(_workflow("Workflow B"))
    return WorkflowEngine(
        repository=WorkflowRepository(),
        registry=registry,
        tasks={TaskType.RESEARCH: _EchoTask(TaskType.RESEARCH)},
        task_executor=TaskExecutor(),
        decision_adapter=decision_adapter,
    )


class _FakeAdapter:
    """Satisfies exactly the shape WorkflowEngine relies on
    (`choose_workflow(request) -> str`) — not RealDecisionAdapter, so these
    tests stay isolated from app.decision entirely."""

    def __init__(self, *, chosen: str | None = None, raises: Exception | None = None) -> None:
        self.chosen = chosen
        self.raises = raises
        self.calls: list[WorkflowRequest] = []

    def choose_workflow(self, request: WorkflowRequest) -> str:
        self.calls.append(request)
        if self.raises is not None:
            raise self.raises
        return self.chosen


async def test_without_an_adapter_uses_the_requested_workflow_name_exactly_as_before():
    engine = _engine(decision_adapter=None)
    request = WorkflowRequest(workflow_name="Workflow A", context=TaskContext())

    response = await engine.execute(request)

    assert response.result.execution.workflow_id == engine.registry.get_active("Workflow A").id


async def test_adapter_returning_a_different_workflow_overrides_the_request():
    adapter = _FakeAdapter(chosen="Workflow B")
    engine = _engine(decision_adapter=adapter)
    request = WorkflowRequest(workflow_name="Workflow A", context=TaskContext())

    response = await engine.execute(request)

    assert adapter.calls == [request]
    assert response.result.execution.workflow_id == engine.registry.get_active("Workflow B").id


async def test_adapter_returning_the_same_workflow_behaves_identically():
    adapter = _FakeAdapter(chosen="Workflow A")
    engine = _engine(decision_adapter=adapter)
    request = WorkflowRequest(workflow_name="Workflow A", context=TaskContext())

    response = await engine.execute(request)

    assert response.result.execution.workflow_id == engine.registry.get_active("Workflow A").id


async def test_adapter_raising_falls_back_to_the_originally_requested_workflow():
    adapter = _FakeAdapter(raises=RuntimeError("decision unavailable"))
    engine = _engine(decision_adapter=adapter)
    request = WorkflowRequest(workflow_name="Workflow A", context=TaskContext())

    response = await engine.execute(request)

    assert response.result.execution.workflow_id == engine.registry.get_active("Workflow A").id


async def test_adapter_choosing_a_nonexistent_workflow_falls_back_to_the_original():
    adapter = _FakeAdapter(chosen="Does Not Exist")
    engine = _engine(decision_adapter=adapter)
    request = WorkflowRequest(workflow_name="Workflow A", context=TaskContext())

    response = await engine.execute(request)

    assert response.result.execution.workflow_id == engine.registry.get_active("Workflow A").id


async def test_when_the_originally_requested_workflow_is_also_missing_it_still_raises():
    """The adapter's failure never suppresses a genuine WorkflowNotFoundError for
    the originally requested workflow — that error is pre-existing behavior."""
    adapter = _FakeAdapter(raises=RuntimeError("boom"))
    engine = _engine(decision_adapter=adapter)

    with pytest.raises(WorkflowNotFoundError):
        await engine.execute(WorkflowRequest(workflow_name="Ghost Workflow", context=TaskContext()))


def _decision_engine_with_recommendation_strategy() -> DecisionEngine:
    engine = DecisionEngine(registry=StrategyRegistry(), repository=DecisionRepository())
    engine.register_strategy(RecommendationStrategy())
    return engine


def test_real_decision_adapter_returns_the_highest_confidence_recommendation():
    decision_engine = _decision_engine_with_recommendation_strategy()
    adapter = RealDecisionAdapter(decision_engine)
    request = WorkflowRequest(
        workflow_name="Workflow A",
        context=TaskContext(
            variables={
                "recommendations": [
                    {"name": "Workflow A", "confidence": 0.4},
                    {"name": "Workflow B", "confidence": 0.9},
                ]
            }
        ),
    )

    assert adapter.choose_workflow(request) == "Workflow B"


def test_real_decision_adapter_raises_when_the_decision_engine_has_no_candidates():
    decision_engine = _decision_engine_with_recommendation_strategy()
    adapter = RealDecisionAdapter(decision_engine)
    request = WorkflowRequest(workflow_name="Workflow A", context=TaskContext())

    with pytest.raises(WorkflowDecisionUnavailableError):
        adapter.choose_workflow(request)


async def test_workflow_engine_end_to_end_with_a_real_decision_adapter():
    decision_engine = _decision_engine_with_recommendation_strategy()
    adapter = RealDecisionAdapter(decision_engine)
    engine = _engine(decision_adapter=adapter)
    context = TaskContext(
        variables={"recommendations": [{"name": "Workflow B", "confidence": 1.0}]}
    )

    response = await engine.execute(WorkflowRequest(workflow_name="Workflow A", context=context))

    assert response.result.execution.workflow_id == engine.registry.get_active("Workflow B").id


def test_workflow_engine_never_imports_app_decision():
    import app.workflows.engine.workflow_engine as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    assert "import app.decision" not in source
    assert "from app.decision" not in source
