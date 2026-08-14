from app.platform.session.execution_session_service import ExecutionSessionService


def build_default_execution_session_service() -> ExecutionSessionService:
    """Composition root for this service. ExecutionSessionService has no
    injected collaborator at all — it is a pure, stateless creator of
    ExecutionSessions — so this factory exists purely for consistency with
    every other module's `build_default_*` composition root, not because
    there is anything to wire.
    """
    return ExecutionSessionService()
