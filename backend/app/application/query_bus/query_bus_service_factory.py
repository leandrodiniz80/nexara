from app.application.bus.bus_execution_service_factory import build_default_bus_execution_service
from app.application.queries.query_registry_service_factory import (
    build_default_query_registry_service,
)
from app.application.query_bus.query_bus import QueryBus
from app.application.query_bus.query_bus_service import QueryBusService


def build_default_query_bus_service() -> QueryBusService:
    """Composition root for this service. Builds QueryRegistryService and
    BusExecutionService exclusively through their own official factories,
    wires them into a QueryBus, and wraps that in a QueryBusService —
    nothing else.
    """
    query_bus = QueryBus(
        query_registry_service=build_default_query_registry_service(),
        bus_execution_service=build_default_bus_execution_service(),
    )
    return QueryBusService(query_bus)
