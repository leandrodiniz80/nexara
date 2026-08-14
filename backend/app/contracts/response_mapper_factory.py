from app.contracts.response_mapper import ResponseMapper


def build_default_response_mapper() -> ResponseMapper:
    """Composition root for this mapper. ResponseMapper has no injected
    collaborator at all — it is a pure, stateless mapper between two
    already-built representations — so this factory exists purely for
    consistency with every other module's `build_default_*` composition
    root, not because there is anything to wire.
    """
    return ResponseMapper()
