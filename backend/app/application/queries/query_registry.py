from pydantic import BaseModel, ConfigDict, Field

from app.application.queries.application_query import ApplicationQuery
from app.shared.registry.registry import Registry


class QueryRegistry(BaseModel):
    """The platform's frozen, complete list of publicly registered queries
    at one point in time. QueryRegistryService always returns a new one,
    built fresh from ApplicationCatalogService's own catalog — never
    edited in place. `queries` remains the exact same public field it
    always was; register/register_many/find/exists/list are now
    implemented by encapsulating a generic Registry[ApplicationQuery]
    rather than reimplementing the same loop CommandRegistry,
    QueryRegistryService, and ModuleRegistry each used to duplicate.
    """

    model_config = ConfigDict(frozen=True)

    queries: tuple[ApplicationQuery, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[ApplicationQuery]:
        return Registry(items=self.queries, key=lambda query: query.name)

    def register(self, query: ApplicationQuery) -> "QueryRegistry":
        return QueryRegistry(queries=tuple(self._as_registry().register(query).list()))

    def register_many(self, queries: list[ApplicationQuery]) -> "QueryRegistry":
        return QueryRegistry(queries=tuple(self._as_registry().register_many(queries).list()))

    def find(self, name: str) -> ApplicationQuery | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def list(self) -> list[ApplicationQuery]:
        return self._as_registry().list()
