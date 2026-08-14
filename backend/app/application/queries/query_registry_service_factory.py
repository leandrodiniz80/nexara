from app.application.catalog.application_catalog_service_factory import (
    build_default_application_catalog_service,
)
from app.application.queries.query_registry_service import QueryRegistryService


def build_default_query_registry_service() -> QueryRegistryService:
    """Composition root for this service. Builds its single collaborator
    exclusively through `build_default_application_catalog_service()` and
    wires nothing else.
    """
    return QueryRegistryService(build_default_application_catalog_service())
