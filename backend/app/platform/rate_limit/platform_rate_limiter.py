import time


class RateLimitExceeded(Exception):
    pass


class PlatformRateLimiter:
    def __init__(self):
        self._requests: dict[str, list[float]] = {}

    def allow(self, key: str, limit: int | None, window_seconds: int) -> bool:
        if limit is None or limit == -1:
            return True

        now = time.time()
        window_start = now - window_seconds

        timestamps = [t for t in self._requests.get(key, []) if t > window_start]

        if len(timestamps) >= limit:
            self._requests[key] = timestamps
            return False

        timestamps.append(now)
        self._requests[key] = timestamps

        return True
