from datetime import datetime, timezone

from app.platform.storage.platform_storage import PlatformStorage

_MAX_IN_MEMORY_EVENTS = 10_000
_DEFAULT_LIMIT = 100


class PlatformAudit:
    def __init__(self, storage: PlatformStorage | None = None):
        self._storage = storage
        self._events: list[dict] = []

        if self._storage is not None:
            data = self._storage.load()
            self._events = data.get("audit_events", [])

    def _persist(self) -> None:
        self._storage.save({"audit_events": self._events})

    def log_event(
        self,
        event: str,
        email: str | None,
        organization_id: str | None,
        metadata: dict | None = None,
    ) -> None:
        self._events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "email": email,
                "organization_id": organization_id,
                "metadata": metadata or {},
            }
        )

        if self._storage is None and len(self._events) > _MAX_IN_MEMORY_EVENTS:
            del self._events[0]

        if self._storage is not None:
            self._persist()

    def get_events(
        self,
        email: str | None = None,
        organization_id: str | None = None,
        event: str | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict]:
        if limit <= 0:
            return []

        results = []

        for record in reversed(self._events):
            if email is not None and record["email"] != email:
                continue
            if organization_id is not None and record["organization_id"] != organization_id:
                continue
            if event is not None and record["event"] != event:
                continue

            results.append(record)

            if len(results) >= limit:
                break

        return results
