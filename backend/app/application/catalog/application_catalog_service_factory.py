from app.application.catalog.application_catalog_service import ApplicationCatalogService
from app.application.public.public_use_case_service_factory import (
    build_default_public_use_case_service,
)


def build_default_application_catalog_service() -> ApplicationCatalogService:
    """Composition root for this service. Builds its single collaborator
    exclusively through `build_default_public_use_case_service()` and
    wires nothing else.
    """
    return ApplicationCatalogService(build_default_public_use_case_service())
