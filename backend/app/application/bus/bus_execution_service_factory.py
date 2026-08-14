from app.application.bus.bus_execution_service import BusExecutionService


def build_default_bus_execution_service() -> BusExecutionService:
    """Composition root for this service. BusExecutionService has no
    collaborators of its own to wire — this factory exists so CommandBus
    and QueryBus's own factories obtain it the same way they obtain every
    other collaborator, exclusively through an official factory.
    """
    return BusExecutionService()
