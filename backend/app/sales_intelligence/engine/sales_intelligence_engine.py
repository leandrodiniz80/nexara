from typing import Any, Literal

from app.sales_intelligence.exceptions.strategy_exceptions import StrategyNotFoundError
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.ranking.ranking_engine import RankingEngine
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.repositories.sales_intelligence_repository import (
    SalesIntelligenceRepository,
)
from app.sales_intelligence.schemas.analysis_result import AnalysisResult
from app.sales_intelligence.schemas.analysis_summary import AnalysisSummary
from app.sales_intelligence.schemas.ranked_item import RankedItem
from app.sales_intelligence.strategies.sales_strategy import SalesStrategy


class SalesIntelligenceEngine:
    """Turns a CommercialProfile into commercial decisions: a score, a set of
    recommendations, and (given several profiles) a ranking. Never sends anything,
    never researches anything, never talks to a provider — every method here is a pure
    function of whatever CommercialProfile(s)/CommercialScore it's given.
    """

    def __init__(
        self,
        strategies: dict[CommercialSegment, SalesStrategy],
        ranking_engine: RankingEngine,
        repository: SalesIntelligenceRepository,
    ) -> None:
        self.strategies = strategies
        self.ranking_engine = ranking_engine
        self.repository = repository

    def _select_strategy(self, segment: CommercialSegment) -> SalesStrategy:
        try:
            return self.strategies[segment]
        except KeyError as exc:
            raise StrategyNotFoundError(segment.value) from exc

    def generate_score(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> CommercialScore:
        strategy = self._select_strategy(profile.segment)
        return strategy.calculate(profile, extra_facts=extra_facts)

    def generate_recommendations(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> list[Recommendation]:
        strategy = self._select_strategy(profile.segment)
        return strategy.recommend(profile, score)

    def analyze_company(
        self,
        profile: CommercialProfile,
        *,
        reference: Any = None,
        extra_facts: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        score = self.generate_score(profile, extra_facts=extra_facts)
        recommendations = self.generate_recommendations(profile, score)
        result = AnalysisResult(
            profile=profile,
            strategy_used=profile.segment,
            score=score,
            recommendations=recommendations,
        )
        if reference is not None:
            self.repository.save(reference, result)
        return result

    def analyze_prospect(
        self,
        profile: CommercialProfile,
        *,
        reference: Any = None,
        extra_facts: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        """Identical operation to analyze_company(): this module has no concept of
        "company" vs "prospect" — that distinction belongs to Prospecting, which this
        module doesn't depend on. Kept as its own method so a caller working with
        Prospect data has a same-named counterpart to reach for.
        """
        return self.analyze_company(profile, reference=reference, extra_facts=extra_facts)

    def rank(
        self,
        items: list[RankedItem],
        *,
        kind: Literal["company", "prospect", "campaign"] = "company",
    ) -> list[RankedItem]:
        if kind == "prospect":
            return self.ranking_engine.rank_prospects(items)
        if kind == "campaign":
            return self.ranking_engine.rank_campaigns(items)
        return self.ranking_engine.rank_companies(items)

    def summary(self, result: AnalysisResult) -> AnalysisSummary:
        top_recommendation = result.recommendations[0] if result.recommendations else None
        priority = (
            top_recommendation.priority if top_recommendation else priority_from_score(result.score)
        )
        narrative = (
            f"Empresa do segmento '{result.profile.segment.value}' com score total "
            f"{result.score.total_score}/100 e {result.score.conversion_probability}% de "
            f"probabilidade de conversão. Prioridade: {priority.value}."
        )
        return AnalysisSummary(
            total_score=result.score.total_score,
            conversion_probability=result.score.conversion_probability,
            priority=priority,
            top_recommendation=top_recommendation.title if top_recommendation else None,
            recommendation_count=len(result.recommendations),
            narrative=narrative,
        )
