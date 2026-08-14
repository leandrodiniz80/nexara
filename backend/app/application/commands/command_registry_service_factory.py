from app.application.catalog.application_catalog_service_factory import (
    build_default_application_catalog_service,
)
from app.application.commands.command_registry_service import CommandRegistryService


def build_default_command_registry_service() -> CommandRegistryService:
    """Composition root for this service. Builds its single collaborator
    exclusively through `build_default_application_catalog_service()` and
    wires nothing else.
    """
    return CommandRegistryService(build_default_application_catalog_service())
