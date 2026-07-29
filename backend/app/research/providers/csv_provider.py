from typing import ClassVar

from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.providers.base.provider_base import ProviderBase
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead


class CSVProvider(ProviderBase):
    """Bulk import from a user-supplied CSV file. Not implemented yet — no connector
    needed here (it's a local file, not a network call), but the method bodies stay
    empty until the column-mapping/parsing logic is designed."""

    source: ClassVar[ResearchSource] = ResearchSource.CSV

    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        raise NotImplementedError("CSVProvider.search() is not implemented yet.")

    async def get_company(self, identifier: str) -> ResearchResult | None:
        raise NotImplementedError("CSVProvider.get_company() is not implemented yet.")

    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        raise NotImplementedError("CSVProvider.search_contacts() is not implemented yet.")

    async def health_check(self) -> bool:
        raise NotImplementedError("CSVProvider.health_check() is not implemented yet.")
