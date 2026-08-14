from app.application.catalog.application_catalog_service import ApplicationCatalogService
from app.application.catalog.application_operation import ApplicationOperation
from app.application.queries.application_query import ApplicationQuery
from app.application.queries.query_registry import QueryRegistry


class QueryRegistryService:
    """The platform's official registry of public queries — pure
    description, nothing else: it never executes a query, never
    integrates with anything, never knows the internal domain. It knows
    exclusively ApplicationCatalogService — not CRM, not Runtime, not
    Workflow, not Presentation, not Contracts.

    `build_registry()` never assembles its list by hand: every
    ApplicationQuery comes from converting one ApplicationOperation
    already returned by ApplicationCatalogService.build_catalog().
    """

    def __init__(self, application_catalog_service: ApplicationCatalogService) -> None:
        self._application_catalog_service = application_catalog_service

    def build_registry(self) -> QueryRegistry:
        catalog = self._application_catalog_service.build_catalog()
        queries = tuple(self._to_query(operation) for operation in catalog.operations)
        return QueryRegistry(queries=queries)

    def list_queries(self) -> tuple[ApplicationQuery, ...]:
        return self.build_registry().queries

    def find(self, name: str) -> ApplicationQuery | None:
        for query in self.list_queries():
            if query.name == name:
                return query
        return None

    def exists(self, name: str) -> bool:
        return self.find(name) is not None

    @staticmethod
    def _to_query(operation: ApplicationOperation) -> ApplicationQuery:
        return ApplicationQuery(
            name=operation.name,
            description=operation.description,
            enabled=operation.enabled,
            operation_name=operation.name,
        )
