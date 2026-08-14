from app.presentation.executive_view_service import ExecutiveViewService


def build_default_executive_view_service() -> ExecutiveViewService:
    """Composition root for this service. ExecutiveViewService has no
    injected collaborator at all — it is a pure, stateless composer over
    already-built Views — so this factory exists purely for consistency
    with every other module's `build_default_*` composition root, not
    because there is anything to wire.
    """
    return ExecutiveViewService()
