from typing import ClassVar

from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.providers.base.provider_base import ProviderBase
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead


class WebsiteProvider(ProviderBase):
    """Generic company-website scraper/parser provider. Not implemented yet."""

    source: ClassVar[ResearchSource] = ResearchSource.WEBSITE

    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        raise NotImplementedError("WebsiteProvider.search() is not implemented yet.")

    async def get_company(self, identifier: str) -> ResearchResult | None:
        raise NotImplementedError("WebsiteProvider.get_company() is not implemented yet.")

    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        raise NotImplementedError("WebsiteProvider.search_contacts() is not implemented yet.")

    async def health_check(self) -> bool:
        raise NotImplementedError("WebsiteProvider.health_check() is not implemented yet.")
