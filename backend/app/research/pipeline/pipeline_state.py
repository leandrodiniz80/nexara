from dataclasses import dataclass, field

from app.research.models.research_result import ResearchResult
from app.research.providers.base.research_provider import ResearchProvider
from app.research.strategies.search_strategy import SearchStrategy


@dataclass
class PipelineState:
    """Working memory threaded through the 9 steps — the *only* thing they share.

    A plain dataclass, not a Pydantic schema: it holds live service objects (a
    SearchStrategy/ResearchProvider instance), not just data crossing a boundary. Each
    step reads the fields the *previous* step produced and writes its own — it never
    reaches into another step's class to do its job, which is what keeps every step
    independently replaceable (see PipelineStep).
    """

    strategy: SearchStrategy | None = None
    provider: ResearchProvider | None = None
    raw_results: list[ResearchResult] = field(default_factory=list)
    valid_results: list[ResearchResult] = field(default_factory=list)
    deduplicated_results: list[ResearchResult] = field(default_factory=list)
    duplicates_removed: int = 0
    scored_results: list[ResearchResult] = field(default_factory=list)
    persisted_results: list[ResearchResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    completed_steps: list[str] = field(default_factory=list)
