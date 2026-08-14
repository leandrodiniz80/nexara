from app.application.query_bus.query_bus import QueryBus
from app.application.query_bus.query_request import QueryRequest
from app.application.query_bus.query_result import QueryResult


class QueryBusService:
    """Thin delegation wrapper around QueryBus — `execute()` only forwards
    to the injected QueryBus and returns exactly what it returns. It knows
    exclusively QueryBus.
    """

    def __init__(self, query_bus: QueryBus) -> None:
        self._query_bus = query_bus

    def execute(self, request: QueryRequest) -> QueryResult:
        return self._query_bus.execute(request)
