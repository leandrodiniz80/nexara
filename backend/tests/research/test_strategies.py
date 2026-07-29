from app.research.models.research_result import ResearchResult
from app.research.providers.base.research_provider import ResearchProvider
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead
from app.research.strategies.search_by_city_strategy import SearchByCityStrategy
from app.research.strategies.search_by_cnae_strategy import SearchByCNAEStrategy
from app.research.strategies.search_by_segment_strategy import SearchBySegmentStrategy
from app.research.strategies.search_nearby_strategy import SearchNearbyStrategy


class _SpyProvider(ResearchProvider):
    def __init__(self) -> None:
        self.received_query: CompanySearchQuery | None = None

    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        self.received_query = query
        return []

    async def get_company(self, identifier: str) -> ResearchResult | None:
        return None

    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        return []

    async def health_check(self) -> bool:
        return True


async def test_search_by_city_strategy_builds_the_right_query():
    provider = _SpyProvider()

    await SearchByCityStrategy().execute(provider, city="Goiânia", state="GO", category="Pet Shop")

    assert provider.received_query.city == "Goiânia"
    assert provider.received_query.state == "GO"
    assert provider.received_query.category == "Pet Shop"


async def test_search_by_segment_strategy_builds_the_right_query():
    provider = _SpyProvider()

    await SearchBySegmentStrategy().execute(provider, segment="Pet Shop", city="Goiânia")

    assert provider.received_query.segment == "Pet Shop"
    assert provider.received_query.city == "Goiânia"


async def test_search_by_cnae_strategy_builds_the_right_query():
    provider = _SpyProvider()

    await SearchByCNAEStrategy().execute(provider, cnae="4789-0/99")

    assert provider.received_query.cnae == "4789-0/99"


async def test_search_nearby_strategy_builds_the_right_query():
    provider = _SpyProvider()

    await SearchNearbyStrategy().execute(provider, latitude=-16.6, longitude=-49.3, radius_km=5)

    assert provider.received_query.latitude == -16.6
    assert provider.received_query.longitude == -49.3
    assert provider.received_query.radius_km == 5
