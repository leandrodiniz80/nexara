from app.research.models.enums import ResearchSource
from app.research.providers.mock_provider import MockProvider
from app.research.schemas.company_search_query import CompanySearchQuery


async def test_search_respects_the_query_limit():
    provider = MockProvider(result_count=50)
    results = await provider.search(CompanySearchQuery(city="Goiânia", state="GO", limit=10))
    assert len(results) == 10


async def test_search_is_deterministic_for_the_same_query():
    provider = MockProvider(result_count=15)
    query = CompanySearchQuery(city="Goiânia", state="GO", category="Agência", limit=15)

    first = await provider.search(query)
    second = await provider.search(query)

    assert [r.model_dump() for r in first] == [r.model_dump() for r in second]


async def test_search_names_every_result_after_the_category_or_segment():
    provider = MockProvider(result_count=5)
    query = CompanySearchQuery(city="Goiânia", category="Agência", limit=5)
    results = await provider.search(query)
    assert all(r.company_name.startswith("Agência ") for r in results)
    assert all(r.city == "Goiânia" for r in results)
    assert all(r.source == ResearchSource.MOCK for r in results)


async def test_search_produces_two_malformed_emails_and_four_duplicates_at_35():
    provider = MockProvider(result_count=35)
    results = await provider.search(CompanySearchQuery(city="Goiânia", state="GO", limit=35))

    assert len(results) == 35

    malformed = [r for r in results if r.emails and "@" not in r.emails[0]]
    assert len(malformed) == 2

    # The last 4 are exact copies of the first 4 (same identity-bearing fields).
    for dup_index, source_index in zip(range(31, 35), range(4)):
        assert results[dup_index].company_name == results[source_index].company_name
        assert results[dup_index].website == results[source_index].website


async def test_health_check_and_unsupported_lookups():
    provider = MockProvider()
    assert await provider.health_check() is True
    assert await provider.get_company("anything") is None
    assert await provider.search_contacts(None) == []  # type: ignore[arg-type]
