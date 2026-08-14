from app.presentation.presentation_coordinator_factory import (
    build_default_presentation_coordinator,
)
from app.presentation.presentation_facade import PresentationFacade


def build_default_presentation_facade() -> PresentationFacade:
    """Composition root for this facade. Builds its single collaborator
    exclusively through `build_default_presentation_coordinator()` and
    wires nothing else.
    """
    return PresentationFacade(build_default_presentation_coordinator())
