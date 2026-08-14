from pydantic import BaseModel

from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.pipeline.strategy_kind import StrategyKind


class PipelineResult(BaseModel):
    """The data outcome of one LeadDiscoveryPipeline run."""

    total_found: int
    total_valid: int
    duplicates_removed: int
    average_score: float
    execution_time: float
    provider_used: ResearchSource
    strategy_used: StrategyKind
    companies: list[ResearchResult]
