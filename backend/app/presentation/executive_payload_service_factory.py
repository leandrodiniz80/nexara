from app.presentation.executive_payload_service import ExecutivePayloadService


def build_default_executive_payload_service() -> ExecutivePayloadService:
    """Composition root for this service. ExecutivePayloadService has no
    injected collaborator at all — it is a pure, stateless transformer over
    an already-built ExecutiveView — so this factory exists purely for
    consistency with every other module's `build_default_*` composition
    root, not because there is anything to wire.
    """
    return ExecutivePayloadService()
