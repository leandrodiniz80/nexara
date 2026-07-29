from abc import ABC, abstractmethod

from app.research.models.research_result import ResearchResult
from app.research.providers.base.research_provider import ResearchProvider


class SearchStrategy(ABC):
    """Knows how to turn one kind of search criteria into a CompanySearchQuery and run
    it against a given provider. ResearchEngine.search_by_city()/search_by_segment()/
    search_by_cnae()/search_nearby() each delegate to one of these rather than building
    the query themselves — adding a new way to search means adding a new strategy, not
    touching the engine.
    """

    @abstractmethod
    async def execute(self, provider: ResearchProvider, **criteria) -> list[ResearchResult]:
        """Build the right query for this strategy from `criteria` and run it."""
