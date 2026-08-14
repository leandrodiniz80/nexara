from abc import ABC, abstractmethod
from typing import Any


class ConnectorBase(ABC):
    """How a provider physically reaches an external system — pure transport, no
    knowledge of "company research" at all. Separated from `providers/` so the same
    connector (e.g. a generic HTTP client) can back more than one provider, and so a
    provider's business logic never has to know about auth headers, retries or
    rate-limiting directly.
    """

    @abstractmethod
    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a read call and return the parsed response body."""

    @abstractmethod
    async def post(self, path: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a write/query call and return the parsed response body."""


class HTTPConnector(ConnectorBase):
    """Generic REST connector. Not implemented yet — no HTTP client, no auth, no
    retries wired up. Every API-based provider (Google Maps/Business, LinkedIn,
    Instagram, Website) will use one of these once real integrations are built.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or {}

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError("HTTPConnector.get() is not implemented yet.")

    async def post(self, path: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError("HTTPConnector.post() is not implemented yet.")
