from app.research.models.research_result import ResearchResult
from app.research.providers.base.research_provider import ResearchProvider
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.strategies.search_strategy import SearchStrategy


class SearchByCityStrategy(SearchStrategy):
    async def execute(
        self,
        provider: ResearchProvider,
        *,
        city: str,
        state: str | None = None,
        category: str | None = None,
        limit: int = 20,
        **_ignored,
    ) -> list[ResearchResult]:
        query = CompanySearchQuery(city=city, state=state, category=category, limit=limit)
        return await provider.search(query)
