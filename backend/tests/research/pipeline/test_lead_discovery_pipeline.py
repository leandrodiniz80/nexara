import uuid
from typing import ClassVar

import pytest

from app.events.bus.event_bus import EventBus
from app.events.handlers.event_handler import EventHandler
from app.events.schemas.domain_event import DomainEvent
from app.research.models.enums import ResearchSource
from app.research.pipeline.factory import build_default_lead_discovery_pipeline
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.pipeline.strategy_kind import StrategyKind
from app.research.providers.mock_provider import MockProvider
from app.research.repositories.research_result_repository import ResearchResultRepository


class _EventRecorder(EventHandler):
    def __init__(self, event_name: str) -> None:
        self.event_name = event_name
        self.received: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.received.append(event)


def _build_pipeline(*, bus: EventBus, repository: ResearchResultRepository, result_count: int):
    return build_default_lead_discovery_pipeline(
        providers={ResearchSource.MOCK: MockProvider(result_count=result_count)},
        repository=repository,
        event_bus=bus,
    )


async def test_pipeline_runs_agencies_in_goiania_end_to_end():
    """The scenario from the task: "Pesquisar agências em Goiânia", 35 results from
    the provider. With MockProvider's built-in, deterministic data-quality issues (2
    malformed emails, 4 exact duplicates copied from the first 4 records — see its own
    docstring), the traced-by-hand outcome is: 35 found, 33 valid (2 dropped for a
    malformed email), 4 of those valid ones collapsed as duplicates, 29 final
    companies, average confidence score ≈ 59.66.
    """
    bus = EventBus()
    started = _EventRecorder("research.started")
    completed = _EventRecorder("research.completed")
    bus.subscribe("research.started", started)
    bus.subscribe("research.completed", completed)
    repository = ResearchResultRepository()
    pipeline = _build_pipeline(bus=bus, repository=repository, result_count=35)

    mission_id = uuid.uuid4()
    context = PipelineContext(
        mission_id=mission_id,
        strategy=StrategyKind.CITY,
        query={"city": "Goiânia", "state": "GO", "category": "Agência", "limit": 35},
    )

    report = await pipeline.execute(context)

    assert report.errors == []
    assert report.steps == [
        "validate_request",
        "select_strategy",
        "select_provider",
        "search_companies",
        "normalize_companies",
        "remove_duplicates",
        "calculate_scores",
        "persist_results",
        "publish_events",
    ]

    result = report.result
    assert result is not None
    assert result.total_found == 35
    assert result.total_valid == 33
    assert result.duplicates_removed == 4
    assert len(result.companies) == 29
    assert result.average_score == pytest.approx(59.66, abs=0.01)
    assert result.provider_used == ResearchSource.MOCK
    assert result.strategy_used == StrategyKind.CITY
    assert result.execution_time >= 0

    # Step 8 actually persisted through ResearchResultRepository, and only that.
    assert len(repository.list_all()) == 29

    # Step 9 actually published through the real EventBus.
    assert len(started.received) == 1
    assert len(completed.received) == 1
    assert started.received[0].aggregate_id == mission_id
    assert completed.received[0].payload["duplicates_removed"] == 4


async def test_report_carries_warnings_for_every_discarded_record():
    bus = EventBus()
    pipeline = _build_pipeline(bus=bus, repository=ResearchResultRepository(), result_count=35)
    context = PipelineContext(
        strategy=StrategyKind.CITY,
        query={"city": "Goiânia", "limit": 35},
    )

    report = await pipeline.execute(context)

    assert len(report.warnings) == 2  # the two malformed-email records


async def test_validation_failure_stops_before_any_search_or_persistence():
    bus = EventBus()
    repository = ResearchResultRepository()
    pipeline = _build_pipeline(bus=bus, repository=repository, result_count=10)
    context = PipelineContext(strategy=StrategyKind.CITY, query={})  # missing "city"

    report = await pipeline.execute(context)

    assert report.result is None
    assert len(report.errors) == 1
    assert report.steps == []
    assert repository.list_all() == []


class _BrokenStep(PipelineStep):
    name: ClassVar[str] = "broken_step"

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        raise RuntimeError("boom")

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        pass


async def test_a_step_failing_after_persist_rolls_back_the_repository():
    from app.research.pipeline.lead_discovery_pipeline import LeadDiscoveryPipeline
    from app.research.pipeline.steps.calculate_scores import CalculateScoresStep
    from app.research.pipeline.steps.normalize_companies import NormalizeCompaniesStep
    from app.research.pipeline.steps.persist_results import PersistResultsStep
    from app.research.pipeline.steps.remove_duplicates import RemoveDuplicatesStep
    from app.research.pipeline.steps.search_companies import SearchCompaniesStep
    from app.research.pipeline.steps.select_provider import SelectProviderStep
    from app.research.pipeline.steps.select_strategy import SelectStrategyStep
    from app.research.pipeline.steps.validate_request import ValidateRequestStep
    from app.research.services.duplicate_detector import DuplicateDetector
    from app.research.services.enrichment_pipeline import EnrichmentPipeline
    from app.research.services.score_calculator import ScoreCalculator

    repository = ResearchResultRepository()
    pipeline = LeadDiscoveryPipeline(
        [
            ValidateRequestStep(),
            SelectStrategyStep(),
            SelectProviderStep({ResearchSource.MOCK: MockProvider(result_count=5)}),
            SearchCompaniesStep(),
            NormalizeCompaniesStep(EnrichmentPipeline()),
            RemoveDuplicatesStep(DuplicateDetector()),
            CalculateScoresStep(ScoreCalculator()),
            PersistResultsStep(repository),
            _BrokenStep(),  # stands in for PublishEventsStep failing
        ]
    )
    context = PipelineContext(
        strategy=StrategyKind.CITY, query={"city": "Goiânia", "limit": 5}
    )

    report = await pipeline.execute(context)

    assert report.result is None
    assert any("boom" in error for error in report.errors)
    # PersistResultsStep.rollback() ran, undoing what it had just saved.
    assert repository.list_all() == []
