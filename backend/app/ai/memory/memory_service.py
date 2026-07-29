from abc import ABC, abstractmethod
from typing import Any


class MemoryService(ABC):
    """Contract for long-term/contextual memory available to agents (e.g. "what do we
    already know about this prospect"). No implementation yet — no store has been
    chosen, so this stays an interface until that decision is made.
    """

    @abstractmethod
    async def save(self, key: str, value: Any, *, namespace: str | None = None) -> None:
        """Persist `value` under `key` (optionally scoped to `namespace`, e.g. a prospect id)."""

    @abstractmethod
    async def load(self, key: str, *, namespace: str | None = None) -> Any | None:
        """Fetch the value stored under `key`, or None if there isn't one."""

    @abstractmethod
    async def search(self, query: str, *, namespace: str | None = None, limit: int = 10) -> list[Any]:
        """Free-text/semantic search over stored memories."""

    @abstractmethod
    async def forget(self, key: str, *, namespace: str | None = None) -> None:
        """Delete the value stored under `key`."""
