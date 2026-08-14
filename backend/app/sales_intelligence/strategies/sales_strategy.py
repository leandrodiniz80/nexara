from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import RecommendationEngine
from app.sales_intelligence.scoring.score_calculator import (
    DEFAULT_TOTAL_SCORE_WEIGHTS,
    ScoreCalculator,
)


class SalesStrategy(ABC):
    """Segment-specific analysis. SalesIntelligenceEngine picks one of these by
    `profile.segment` — this is the Strategy Pattern the module asks for."""

    segment: ClassVar[CommercialSegment]

    @abstractmethod
    def analyze(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Segment-specific facts extracted from the profile, feeding calculate()/recommend()."""

    @abstractmethod
    def calculate(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> CommercialScore:
        """Segment-tuned scoring."""

    @abstractmethod
    def recommend(self, profile: CommercialProfile, score: CommercialScore) -> list[Recommendation]:
        """Segment-tuned recommendations."""


class SalesStrategyBase(SalesStrategy):
    """Shared composition every concrete strategy builds on: reuses the same
    ScoreCalculator/RecommendationEngine everything else uses (no duplicated scoring
    logic per segment), and only lets a concrete strategy override two things: its own
    `_weights` for combining the five score components into total_score, and one
    `_flavor_recommendation()` on top of the generic three RecommendationEngine already
    produces. That's the whole difference between e.g. RetailStrategy and
    CorporateStrategy — which is exactly how much a segment *should* differ here.
    """

    _weights: ClassVar[dict[str, float]] = DEFAULT_TOTAL_SCORE_WEIGHTS

    def __init__(
        self, score_calculator: ScoreCalculator, recommendation_engine: RecommendationEngine
    ) -> None:
        self.score_calculator = score_calculator
        self.recommendation_engine = recommendation_engine

    def analyze(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        facts = dict(extra_facts or {})
        facts["segment_strategy"] = self.segment.value
        return facts

    def calculate(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> CommercialScore:
        facts = self.analyze(profile, extra_facts=extra_facts)
        company = self.score_calculator.calculate_company_score(profile, extra_facts=facts)
        potential = self.score_calculator.calculate_potential(profile, extra_facts=facts)
        urgency = self.score_calculator.calculate_urgency(profile, extra_facts=facts)
        visibility = self.score_calculator.calculate_visibility(profile, extra_facts=facts)
        relationship = self.score_calculator.calculate_relationship(profile, extra_facts=facts)
        conversion = self.score_calculator.calculate_conversion_probability(
            profile, extra_facts=facts
        )
        total = self.score_calculator.calculate_total_score(
            company_score=company,
            potential_score=potential,
            urgency_score=urgency,
            visibility_score=visibility,
            relationship_score=relationship,
            weights=self._weights,
        )
        return CommercialScore(
            company_score=company,
            potential_score=potential,
            urgency_score=urgency,
            visibility_score=visibility,
            relationship_score=relationship,
            conversion_probability=conversion,
            total_score=total,
        )

    def recommend(self, profile: CommercialProfile, score: CommercialScore) -> list[Recommendation]:
        recommendations = self.recommendation_engine.build_recommendations(profile, score)
        recommendations.append(self._flavor_recommendation(profile, score))
        return recommendations

    @abstractmethod
    def _flavor_recommendation(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> Recommendation:
        """The one segment-specific recommendation each concrete strategy must supply."""
