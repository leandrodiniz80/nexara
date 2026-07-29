from app.research.engine.research_engine import ResearchEngine
from app.research.models.enums import ResearchSource
from app.research.providers.base.research_provider import ResearchProvider
from app.research.providers.csv_provider import CSVProvider
from app.research.providers.google_business_provider import GoogleBusinessProvider
from app.research.providers.google_maps_provider import GoogleMapsProvider
from app.research.providers.instagram_provider import InstagramProvider
from app.research.providers.linkedin_provider import LinkedInProvider
from app.research.providers.manual_provider import ManualProvider
from app.research.providers.website_provider import WebsiteProvider
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.research.services.duplicate_detector import DuplicateDetector
from app.research.services.enrichment_pipeline import EnrichmentPipeline
from app.research.services.score_calculator import ScoreCalculator


def build_default_research_engine(
    *, providers: dict[ResearchSource, ResearchProvider] | None = None
) -> ResearchEngine:
    """Composition root for the Research Engine module — the one place that decides
    which concrete providers back a ResearchEngine. Registers every provider by
    default; all of them raise NotImplementedError today. Swap one for a real
    implementation here later without touching engine/strategy/service code.
    """
    providers = (
        providers
        if providers is not None
        else {
            ResearchSource.GOOGLE_MAPS: GoogleMapsProvider(),
            ResearchSource.GOOGLE_BUSINESS: GoogleBusinessProvider(),
            ResearchSource.LINKEDIN: LinkedInProvider(),
            ResearchSource.INSTAGRAM: InstagramProvider(),
            ResearchSource.WEBSITE: WebsiteProvider(),
            ResearchSource.CSV: CSVProvider(),
            ResearchSource.MANUAL: ManualProvider(),
        }
    )
    return ResearchEngine(
        providers=providers,
        repository=ResearchResultRepository(),
        duplicate_detector=DuplicateDetector(),
        enrichment_pipeline=EnrichmentPipeline(),
        score_calculator=ScoreCalculator(),
    )
