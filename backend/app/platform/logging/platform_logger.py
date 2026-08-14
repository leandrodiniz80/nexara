from datetime import datetime, timezone

_MAX_LOGS = 10_000
_DEFAULT_LIMIT = 100


class PlatformLogger:
    def __init__(self):
        self._logs: list[dict] = []

    def log(
        self,
        level: str,
        message: str,
        *,
        correlation_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._logs.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "message": message,
                "correlation_id": correlation_id,
                "metadata": metadata or {},
            }
        )

        if len(self._logs) > _MAX_LOGS:
            del self._logs[0]

    def get_logs(
        self,
        level: str | None = None,
        organization_id: str | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict]:
        if limit <= 0:
            return []

        results = []

        for record in reversed(self._logs):
            if level is not None and record["level"] != level:
                continue
            record_org = record["metadata"].get("organization_id")
            if organization_id is not None and record_org != organization_id:
                continue

            results.append(record)

            if len(results) >= limit:
                break

        return results
