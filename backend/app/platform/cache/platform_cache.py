import time
from typing import Any


class PlatformCache:
    def get(self, key: str) -> Any:
        return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        pass

    def delete(self, key: str) -> None:
        pass


class InMemoryCache(PlatformCache):
    def __init__(self):
        self._data: dict[str, tuple[Any, float | None]] = {}

    def get(self, key: str) -> Any:
        entry = self._data.get(key)

        if entry is None:
            return None

        value, expires_at = entry

        if expires_at is not None and time.time() >= expires_at:
            del self._data[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires_at = time.time() + ttl if ttl is not None else None
        self._data[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
