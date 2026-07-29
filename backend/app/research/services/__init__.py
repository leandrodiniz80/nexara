from app.research.services.duplicate_detector import DuplicateDetector
from app.research.services.enrichment_pipeline import EnrichmentPipeline
from app.research.services.research_engine_factory import build_default_research_engine
from app.research.services.score_calculator import ScoreCalculator

__all__ = [
    "DuplicateDetector",
    "EnrichmentPipeline",
    "ScoreCalculator",
    "build_default_research_engine",
]
