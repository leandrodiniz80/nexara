import json

import pytest

from app.research.engine.research_engine import ResearchEngine
from app.research.exceptions.provider_exceptions import NoProviderAvailableError, ProviderNotAvailableError
from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.providers.base.research_provider import ResearchProvider
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead
from app.research.services.duplicate_detector import DuplicateDetector
from app.research.services.enrichment_pipeline import EnrichmentPipeline
from app.research.services.score_calculator import ScoreCalculator

VALID_CNPJ = "11.222.333/0001-81"


class _CannedProvider(ResearchProvider):
    def __init__(self, results: list[ResearchResult]) -> None:
        self._results = results
        self.last_query: CompanySearchQuery | None = None

    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        self.last_query = query
        return list(self._results)

    async def get_company(self, identifier: str) -> ResearchResult | None:
        return next((r for r in self._results if r.cnpj == identifier), None)

    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        return []

    async def health_check(self) -> bool:
        return True


def _build_engine(providers: dict[ResearchSource, ResearchProvider]) -> ResearchEngine:
    return ResearchEngine(
        providers=providers,
        repository=ResearchResultRepository(),
        duplicate_detector=DuplicateDetector(),
        enrichment_pipeline=EnrichmentPipeline(),
        score_calculator=ScoreCalculator(),
    )


async def test_search_by_city_routes_to_the_right_provider_and_stores_results():
    found = ResearchResult(
        company_name="Pet Shop Amigo Fiel", city="Goiânia", source=ResearchSource.GOOGLE_MAPS
    )
    provider = _CannedProvider([found])
    engine = _build_engine({ResearchSource.GOOGLE_MAPS: provider})

    results = await engine.search_by_city("Goiânia", "GO", source=ResearchSource.GOOGLE_MAPS)

    assert results == [found]
    assert provider.last_query.city == "Goiânia"
    assert engine.repository.list_all() == [found]


async def test_select_provider_raises_when_source_not_registered():
    engine = _build_engine({ResearchSource.GOOGLE_MAPS: _CannedProvider([])})

    with pytest.raises(ProviderNotAvailableError):
        await engine.search_by_city("Goiânia", source=ResearchSource.LINKEDIN)


async def test_select_provider_raises_when_no_providers_registered():
    engine = _build_engine({})

    with pytest.raises(NoProviderAvailableError):
        await engine.search_by_city("Goiânia")


def test_merge_results_combines_batches_without_deduplicating():
    engine = _build_engine({})
    batch_a = [ResearchResult(company_name="A", source=ResearchSource.GOOGLE_MAPS)]
    batch_b = [ResearchResult(company_name="B", source=ResearchSource.INSTAGRAM)]

    merged = engine.merge_results(batch_a, batch_b)

    assert merged == batch_a + batch_b


def test_remove_duplicates_collapses_matching_cnpj_and_keeps_singles():
    engine = _build_engine({})
    a = ResearchResult(
        company_name="Pet Shop", cnpj=VALID_CNPJ, source=ResearchSource.GOOGLE_MAPS, confidence_score=40
    )
    b = ResearchResult(
        company_name="Pet Shop", cnpj=VALID_CNPJ, source=ResearchSource.INSTAGRAM, confidence_score=80
    )
    c = ResearchResult(company_name="Padaria", city="Goiânia", state="GO", source=ResearchSource.WEBSITE)

    deduplicated = engine.remove_duplicates([a, b, c])

    assert len(deduplicated) == 2
    assert c in deduplicated
    merged = next(r for r in deduplicated if r is not c)
    assert merged.confidence_score == 80
    assert merged.cnpj == VALID_CNPJ


def test_calculate_scores_sets_confidence_score_in_place():
    engine = _build_engine({})
    bare = ResearchResult(company_name="Empresa", source=ResearchSource.MANUAL)

    scored = engine.calculate_scores([bare])

    assert scored[0].confidence_score == 0
    assert bare.confidence_score == 0


def test_export_json_round_trips():
    engine = _build_engine({})
    result = ResearchResult(company_name="Empresa", city="Goiânia", source=ResearchSource.MANUAL)

    payload = json.loads(engine.export([result], fmt="json"))

    assert payload[0]["company_name"] == "Empresa"
    assert payload[0]["city"] == "Goiânia"


def test_export_csv_has_header_and_row():
    engine = _build_engine({})
    result = ResearchResult(
        company_name="Empresa", city="Goiânia", phones=["123", "456"], source=ResearchSource.MANUAL
    )

    lines = engine.export([result], fmt="csv").strip().splitlines()

    assert lines[0].startswith("company_name")
    assert "Empresa" in lines[1]
    assert "123;456" in lines[1]


def test_export_rejects_unknown_format():
    engine = _build_engine({})
    with pytest.raises(ValueError):
        engine.export([], fmt="xml")  # type: ignore[arg-type]
