import uuid

import pytest

from app.events.bus.event_bus import EventBus
from app.events.handlers.event_handler import EventHandler
from app.events.publishers.event_publisher import EventPublisher
from app.events.schemas.domain_event import DomainEvent
from app.research.exceptions.provider_exceptions import ProviderNotAvailableError
from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.pipeline.exceptions import PipelineValidationError
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.steps.calculate_scores import CalculateScoresStep
from app.research.pipeline.steps.normalize_companies import NormalizeCompaniesStep
from app.research.pipeline.steps.persist_results import PersistResultsStep
from app.research.pipeline.steps.publish_events import PublishEventsStep
from app.research.pipeline.steps.remove_duplicates import RemoveDuplicatesStep
from app.research.pipeline.steps.search_companies import SearchCompaniesStep
from app.research.pipeline.steps.select_provider import SelectProviderStep
from app.research.pipeline.steps.select_strategy import SelectStrategyStep
from app.research.pipeline.steps.validate_request import ValidateRequestStep
from app.research.pipeline.strategy_kind import StrategyKind
from app.research.providers.mock_provider import MockProvider
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.research.services.duplicate_detector import DuplicateDetector
from app.research.services.enrichment_pipeline import EnrichmentPipeline
from app.research.services.score_calculator import ScoreCalculator
from app.research.strategies.search_by_city_strategy import SearchByCityStrategy


def _context(**overrides) -> PipelineContext:
    defaults = dict(strategy=StrategyKind.CITY, query={"city": "Goiânia", "state": "GO"})
    defaults.update(overrides)
    return PipelineContext(**defaults)


def _result(**overrides) -> ResearchResult:
    defaults = dict(company_name="Empresa Teste", source=ResearchSource.MOCK)
    defaults.update(overrides)
    return ResearchResult(**defaults)


# ---------- Step 1 ----------


async def test_validate_request_passes_when_required_fields_are_present():
    step = ValidateRequestStep()
    state = await step.execute(_context(), PipelineState())
    assert state.completed_steps == ["validate_request"]


async def test_validate_request_raises_when_a_required_field_is_missing():
    step = ValidateRequestStep()
    context = _context(strategy=StrategyKind.CITY, query={})
    with pytest.raises(PipelineValidationError):
        await step.execute(context, PipelineState())


# ---------- Step 2 ----------


async def test_select_strategy_instantiates_the_right_class():
    step = SelectStrategyStep()
    state = await step.execute(_context(strategy=StrategyKind.CITY), PipelineState())
    assert isinstance(state.strategy, SearchByCityStrategy)


# ---------- Step 3 ----------


async def test_select_provider_defaults_to_mock_when_context_names_none():
    provider = MockProvider()
    step = SelectProviderStep({ResearchSource.MOCK: provider})
    state = await step.execute(_context(provider=None), PipelineState())
    assert state.provider is provider


async def test_select_provider_raises_for_an_unregistered_source():
    step = SelectProviderStep({ResearchSource.MOCK: MockProvider()})
    context = _context(provider=ResearchSource.GOOGLE_MAPS)
    with pytest.raises(ProviderNotAvailableError):
        await step.execute(context, PipelineState())


# ---------- Step 4 ----------


async def test_search_companies_delegates_to_the_selected_strategy_and_provider():
    state = PipelineState(strategy=SearchByCityStrategy(), provider=MockProvider(result_count=5))
    context = _context(query={"city": "Goiânia", "state": "GO", "limit": 5})

    state = await SearchCompaniesStep().execute(context, state)

    assert len(state.raw_results) == 5
    assert all(r.city == "Goiânia" for r in state.raw_results)


# ---------- Step 5 ----------


async def test_normalize_companies_drops_malformed_emails_and_reports_a_warning():
    state = PipelineState(
        raw_results=[
            _result(company_name="Boa", emails=["contato@empresa.com"]),
            _result(company_name="Ruim", emails=["sem-arroba"]),
        ]
    )
    state = await NormalizeCompaniesStep(EnrichmentPipeline()).execute(_context(), state)

    assert [r.company_name for r in state.valid_results] == ["Boa"]
    assert len(state.warnings) == 1
    assert "Ruim" in state.warnings[0]


# ---------- Step 6 ----------


async def test_remove_duplicates_collapses_a_pair_and_counts_it():
    same = dict(company_name="Empresa X", city="Goiânia", state="GO", website="https://x.com.br")
    duplicates = [_result(**same), _result(**same), _result(company_name="Y")]
    state = PipelineState(valid_results=duplicates)

    state = await RemoveDuplicatesStep(DuplicateDetector()).execute(_context(), state)

    assert len(state.deduplicated_results) == 2
    assert state.duplicates_removed == 1


# ---------- Step 7 ----------


async def test_calculate_scores_sets_confidence_score_on_every_result():
    state = PipelineState(deduplicated_results=[_result(city="Goiânia", category="Agência")])
    state = await CalculateScoresStep(ScoreCalculator()).execute(_context(), state)

    assert state.scored_results[0].confidence_score is not None
    assert 0 <= state.scored_results[0].confidence_score <= 100


# ---------- Step 8 ----------


async def test_persist_results_saves_into_the_repository_and_rollback_removes_them():
    repository = ResearchResultRepository()
    state = PipelineState(scored_results=[_result()])
    step = PersistResultsStep(repository)

    state = await step.execute(_context(), state)
    assert len(repository.list_all()) == 1

    await step.rollback(_context(), state)
    assert repository.list_all() == []


# ---------- Step 9 ----------


class _Collector(EventHandler):
    def __init__(self, event_name: str) -> None:
        self.event_name = event_name
        self.received: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.received.append(event)


async def test_publish_events_emits_started_then_completed_with_causation_linked():
    bus = EventBus()
    started_collector = _Collector("research.started")
    completed_collector = _Collector("research.completed")
    bus.subscribe("research.started", started_collector)
    bus.subscribe("research.completed", completed_collector)

    mission_id = uuid.uuid4()
    context = _context(mission_id=mission_id, query={"city": "Goiânia"})
    state = PipelineState(
        raw_results=[_result(), _result()],
        duplicates_removed=1,
        scored_results=[_result(confidence_score=80), _result(confidence_score=60)],
    )

    await PublishEventsStep(EventPublisher(bus)).execute(context, state)

    assert len(started_collector.received) == 1
    assert len(completed_collector.received) == 1
    started = started_collector.received[0]
    completed = completed_collector.received[0]
    assert started.aggregate_id == mission_id
    assert completed.aggregate_id == mission_id
    assert completed.payload["results_found"] == 2
    assert completed.payload["duplicates_removed"] == 1
    assert completed.payload["average_score"] == 70.0
    assert completed.metadata["causation_id"] == started.event_id
