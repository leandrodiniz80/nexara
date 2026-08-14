from app.research.models.research_result import ResearchResult


def average_score(results: list[ResearchResult]) -> float:
    """Shared by PublishEventsStep (event payload) and LeadDiscoveryPipeline
    (PipelineResult) so both ever report the exact same number."""
    scored = [r.confidence_score for r in results if r.confidence_score is not None]
    return round(sum(scored) / len(scored), 2) if scored else 0.0
