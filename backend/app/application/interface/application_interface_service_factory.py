from app.application.interface.application_interface_service import ApplicationInterfaceService
from app.interface.platform_interface_factory import build_default_platform_interface


def build_default_application_interface_service() -> ApplicationInterfaceService:
    """Composition root for this service. Builds its single collaborator
    exclusively through `build_default_platform_interface()` and wires
    nothing else.
    """
    return ApplicationInterfaceService(build_default_platform_interface())
