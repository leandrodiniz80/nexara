from app.operations.engine.operations_engine import OperationsEngine
from app.operations.repositories.operation_repository import OperationRepository


def build_default_operations_engine() -> OperationsEngine:
    """Composition root for this engine. Builds a fresh, empty
    OperationRepository and wires nothing else — this module integrates
    with nothing outside itself.
    """
    return OperationsEngine(OperationRepository())
