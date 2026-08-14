from app.research.models.research_result import ResearchResult
from app.research.providers.base.research_provider import ResearchProvider
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.strategies.search_strategy import SearchStrategy


class SearchNearbyStrategy(SearchStrategy):
    async def execute(
        self,
        provider: ResearchProvider,
        *,
        latitude: float,
        longitude: float,
        radius_km: float,
        category: str | None = None,
        limit: int = 20,
        **_ignored,
    ) -> list[ResearchResult]:
        query = CompanySearchQuery(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            category=category,
            limit=limit,
        )
        return await provider.search(query)
