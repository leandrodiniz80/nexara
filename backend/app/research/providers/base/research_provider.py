from abc import ABC, abstractmethod

from app.research.models.research_result import ResearchResult
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead


class ResearchProvider(ABC):
    """Contract every research provider (Google Maps, LinkedIn, a CSV import, a human
    doing manual entry, ...) must satisfy.

    Research Engine only ever talks to providers through this interface — it has no
    idea which concrete provider it's using, which is what lets a new source be added
    (or a fake one used in tests) without touching engine/strategy code.
    """

    @abstractmethod
    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        """Find companies matching `query`."""

    @abstractmethod
    async def get_company(self, identifier: str) -> ResearchResult | None:
        """Fetch one company by a provider-specific identifier (place id, CNPJ, URL, ...)."""

    @abstractmethod
    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        """Find people associated with `company`."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Whether this provider is currently reachable/usable."""
