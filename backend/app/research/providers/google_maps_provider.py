from typing import ClassVar

from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.providers.base.provider_base import ProviderBase
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead


class GoogleMapsProvider(ProviderBase):
    """Google Maps / Places provider. Not implemented yet."""

    source: ClassVar[ResearchSource] = ResearchSource.GOOGLE_MAPS

    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        raise NotImplementedError("GoogleMapsProvider.search() is not implemented yet.")

    async def get_company(self, identifier: str) -> ResearchResult | None:
        raise NotImplementedError("GoogleMapsProvider.get_company() is not implemented yet.")

    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        raise NotImplementedError("GoogleMapsProvider.search_contacts() is not implemented yet.")

    async def health_check(self) -> bool:
        raise NotImplementedError("GoogleMapsProvider.health_check() is not implemented yet.")
