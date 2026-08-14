from datetime import datetime, timezone
from typing import Any

from app.platform.session.execution_session import ExecutionSession


class ExecutionSessionService:
    """Creates and finishes ExecutionSessions — nothing more. It knows no
    domain (not Runtime, Operations, Decision, Workflow, CRM, or
    Observability): it only tracks that one execution happened. `finish()`
    never alters the given ExecutionSession, it always returns a new one
    with `finished_at` set.
    """

    def create(
        self,
        *,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ExecutionSession:
        now = now or datetime.now(timezone.utc)
        return ExecutionSession(request_id=request_id, started_at=now, metadata=metadata or {})

    def finish(
        self, session: ExecutionSession, *, now: datetime | None = None
    ) -> ExecutionSession:
        now = now or datetime.now(timezone.utc)
        return ExecutionSession(
            session_id=session.session_id,
            request_id=session.request_id,
            started_at=session.started_at,
            finished_at=now,
            metadata=session.metadata,
        )
