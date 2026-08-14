from app.events.bus.event_bus import EventBus
from app.events.publishers.event_publisher import EventPublisher
from app.research.models.enums import ResearchSource
from app.research.pipeline.lead_discovery_pipeline import LeadDiscoveryPipeline
from app.research.pipeline.steps.calculate_scores import CalculateScoresStep
from app.research.pipeline.steps.normalize_companies import NormalizeCompaniesStep
from app.research.pipeline.steps.persist_results import PersistResultsStep
from app.research.pipeline.steps.publish_events import PublishEventsStep
from app.research.pipeline.steps.remove_duplicates import RemoveDuplicatesStep
from app.research.pipeline.steps.search_companies import SearchCompaniesStep
from app.research.pipeline.steps.select_provider import SelectProviderStep
from app.research.pipeline.steps.select_strategy import SelectStrategyStep
from app.research.pipeline.steps.validate_request import ValidateRequestStep
from app.research.providers.base.research_provider import ResearchProvider
from app.research.providers.mock_provider import MockProvider
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.research.services.duplicate_detector import DuplicateDetector
from app.research.services.enrichment_pipeline import EnrichmentPipeline
from app.research.services.score_calculator import ScoreCalculator


def build_default_lead_discovery_pipeline(
    *,
    providers: dict[ResearchSource, ResearchProvider] | None = None,
    repository: ResearchResultRepository | None = None,
    event_bus: EventBus | None = None,
) -> LeadDiscoveryPipeline:
    """Composition root for this feature: wires the 9 steps, in order, with a
    MockProvider as the only registered provider (this phase has no real
    integrations). Pass `event_bus` to have the pipeline publish onto the
    application's shared bus instead of a fresh, isolated one.
    """
    providers = providers if providers is not None else {ResearchSource.MOCK: MockProvider()}
    repository = repository if repository is not None else ResearchResultRepository()
    publisher = EventPublisher(event_bus or EventBus())

    steps = [
        ValidateRequestStep(),
        SelectStrategyStep(),
        SelectProviderStep(providers),
        SearchCompaniesStep(),
        NormalizeCompaniesStep(EnrichmentPipeline()),
        RemoveDuplicatesStep(DuplicateDetector()),
        CalculateScoresStep(ScoreCalculator()),
        PersistResultsStep(repository),
        PublishEventsStep(publisher),
    ]
    return LeadDiscoveryPipeline(steps)
