from app.presentation.presentation_service import PresentationService


def build_default_presentation_service() -> PresentationService:
    """Composition root for this service. PresentationService has no
    injected collaborator at all — it is a pure, stateless converter over
    already-built domain models — so this factory exists purely for
    consistency with every other module's `build_default_*` composition
    root, not because there is anything to wire.
    """
    return PresentationService()
