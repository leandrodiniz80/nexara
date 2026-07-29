from typing import ClassVar

from app.research.connectors.base.connector_base import ConnectorBase
from app.research.models.enums import ResearchSource
from app.research.providers.base.research_provider import ResearchProvider


class ProviderBase(ResearchProvider):
    """Shared plumbing for every concrete provider: identity and an optional connector.

    Deliberately does not implement any of ResearchProvider's abstract methods — every
    concrete provider still must (Python's ABC machinery enforces this at instantiation
    time), this class only removes the boilerplate around it.
    """

    source: ClassVar[ResearchSource]

    def __init__(self, *, connector: ConnectorBase | None = None) -> None:
        self.connector = connector

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source={self.source.value!r}>"
