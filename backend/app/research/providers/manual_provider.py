from typing import ClassVar

from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.providers.base.provider_base import ProviderBase
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead


class ManualProvider(ProviderBase):
    """A human researcher entering a company by hand — no automation at all. Still
    implements the same interface as every other provider so the rest of the engine
    (dedup, enrichment, scoring, export) treats manual entries identically to an
    automated find. Not implemented yet."""

    source: ClassVar[ResearchSource] = ResearchSource.MANUAL

    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        raise NotImplementedError("ManualProvider.search() is not implemented yet.")

    async def get_company(self, identifier: str) -> ResearchResult | None:
        raise NotImplementedError("ManualProvider.get_company() is not implemented yet.")

    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        raise NotImplementedError("ManualProvider.search_contacts() is not implemented yet.")

    async def health_check(self) -> bool:
        raise NotImplementedError("ManualProvider.health_check() is not implemented yet.")
