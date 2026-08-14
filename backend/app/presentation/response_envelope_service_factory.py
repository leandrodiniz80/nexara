from app.presentation.response_envelope_service import ResponseEnvelopeService


def build_default_response_envelope_service() -> ResponseEnvelopeService:
    """Composition root for this service. ResponseEnvelopeService has no
    injected collaborator at all — it is a pure, stateless wrapper over an
    already-built ExecutivePayload — so this factory exists purely for
    consistency with every other module's `build_default_*` composition
    root, not because there is anything to wire.
    """
    return ResponseEnvelopeService()
