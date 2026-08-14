from app.presentation.executive_payload_service_factory import (
    build_default_executive_payload_service,
)
from app.presentation.executive_view_service_factory import build_default_executive_view_service
from app.presentation.presentation_coordinator import PresentationCoordinator
from app.presentation.response_envelope_service_factory import (
    build_default_response_envelope_service,
)


def build_default_presentation_coordinator() -> PresentationCoordinator:
    """Composition root for this coordinator. Builds each of its three
    collaborators exclusively through their own official factories —
    ExecutiveViewService, ExecutivePayloadService and
    ResponseEnvelopeService — and wires nothing else.
    """
    return PresentationCoordinator(
        executive_view_service=build_default_executive_view_service(),
        executive_payload_service=build_default_executive_payload_service(),
        response_envelope_service=build_default_response_envelope_service(),
    )
