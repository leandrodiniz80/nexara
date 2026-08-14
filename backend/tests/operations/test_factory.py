from app.operations.engine.operations_engine import OperationsEngine
from app.operations.models.enums import OperationState
from app.operations.repositories.operation_repository import OperationRepository
from app.operations.services.operations_engine_factory import build_default_operations_engine


def test_build_default_operations_engine_returns_a_usable_engine():
    engine = build_default_operations_engine()

    assert isinstance(engine, OperationsEngine)
    assert isinstance(engine.operation_repository, OperationRepository)
    assert engine.list_operations() == []


def test_build_default_operations_engine_starts_with_an_empty_repository():
    engine = build_default_operations_engine()

    summary = engine.summary()

    assert summary.total_operations == 0


def test_build_default_operations_engine_is_fully_usable_end_to_end():
    engine = build_default_operations_engine()

    operation = engine.create_operation("Sync inventory")
    started = engine.start_operation(operation.id)
    finished = engine.finish_operation(operation.id)

    assert started.status == OperationState.RUNNING
    assert finished.status == OperationState.FINISHED


def test_build_default_operations_engine_returns_a_fresh_engine_each_call():
    first = build_default_operations_engine()
    first.create_operation("First")

    second = build_default_operations_engine()

    assert second.list_operations() == []
