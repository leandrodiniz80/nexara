from pydantic import BaseModel, ConfigDict

from app.application.bus.bus_execution import BusExecution
from app.application.bus.bus_execution_service import BusExecutionService
from app.application.queries.query_registry_service import QueryRegistryService
from app.application.query_bus.query_request import QueryRequest
from app.application.query_bus.query_result import QueryResult

_QUERY_NOT_FOUND_REASON = "Query not found."
_QUERY_HANDLER_NOT_REGISTERED_REASON = "Query handler not registered."


def _to_query_result(execution: BusExecution) -> QueryResult:
    return QueryResult(
        success=execution.success,
        query_name=execution.name,
        payload=execution.payload,
        reason=execution.reason,
        execution_time=execution.duration,
    )


class QueryBus(BaseModel):
    """The platform's single official dispatch infrastructure for public
    queries — a frozen model holding exactly two collaborators. This
    sprint, it never executes a query: no QueryHandler infrastructure
    exists yet, so it only validates that a requested query is registered
    and, when it is, reports that no handler exists for it. It knows
    exclusively QueryRegistryService and BusExecutionService — not CRM,
    not Runtime, not Workflow, not Presentation, not Contracts, not
    CommandBus, not HandlerRegistryService.

    Unlike CommandBus, this bus wraps nothing around the record
    BusExecutionService.finish() returns: it uses that BusExecution
    directly, since QueryResult's field names already match BusExecution's
    generic shape.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    query_registry_service: QueryRegistryService
    bus_execution_service: BusExecutionService

    def execute(self, request: QueryRequest) -> QueryResult:
        start = self.bus_execution_service.start(request.query_name)

        if not self.query_registry_service.exists(request.query_name):
            return _to_query_result(
                self.bus_execution_service.finish(
                    start, success=False, payload=None, reason=_QUERY_NOT_FOUND_REASON
                )
            )

        return _to_query_result(
            self.bus_execution_service.finish(
                start,
                success=False,
                payload=None,
                reason=_QUERY_HANDLER_NOT_REGISTERED_REASON,
            )
        )
