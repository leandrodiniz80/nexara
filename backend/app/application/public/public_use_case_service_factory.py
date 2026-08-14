from app.application.interface.application_interface_service_factory import (
    build_default_application_interface_service,
)
from app.application.public.public_use_case_service import PublicUseCaseService
from app.operations.coordinator.operations_coordinator_factory import (
    build_default_operations_coordinator,
)


def build_default_public_use_case_service() -> PublicUseCaseService:
    """Composition root for this service. Builds its two collaborators
    exclusively through their own official factories —
    `build_default_application_interface_service()` and
    `build_default_operations_coordinator()` — and wires nothing else.
    """
    return PublicUseCaseService(
        build_default_application_interface_service(),
        build_default_operations_coordinator(),
    )
