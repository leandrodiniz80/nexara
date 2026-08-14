from app.contracts.response_mapper_factory import build_default_response_mapper
from app.interface.platform_interface import PlatformInterface
from app.presentation.presentation_facade_factory import build_default_presentation_facade


def build_default_platform_interface() -> PlatformInterface:
    """Composition root for this interface. Builds each of its two
    collaborators exclusively through their own official factories —
    build_default_presentation_facade() and build_default_response_mapper()
    — and wires nothing else.
    """
    return PlatformInterface(
        presentation_facade=build_default_presentation_facade(),
        response_mapper=build_default_response_mapper(),
    )
