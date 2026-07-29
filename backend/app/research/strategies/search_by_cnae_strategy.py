from app.research.models.research_result import ResearchResult
from app.research.providers.base.research_provider import ResearchProvider
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.strategies.search_strategy import SearchStrategy


class SearchByCNAEStrategy(SearchStrategy):
    async def execute(
        self,
        provider: ResearchProvider,
        *,
        cnae: str,
        city: str | None = None,
        state: str | None = None,
        limit: int = 20,
        **_ignored,
    ) -> list[ResearchResult]:
        query = CompanySearchQuery(cnae=cnae, city=city, state=state, limit=limit)
        return await provider.search(query)
