from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class RealEstateStrategy(SalesStrategyBase):
    """Real estate deals are time-sensitive to launches/inventory — urgency_score
    weighted highest."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.REAL_ESTATE
    _weights: ClassVar[dict[str, float]] = {
        "company_score": 0.25,
        "potential_score": 0.15,
        "urgency_score": 0.30,
        "visibility_score": 0.15,
        "relationship_score": 0.15,
    }

    def _flavor_recommendation(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> Recommendation:
        return Recommendation(
            title="Aproveitar a sazonalidade do lançamento/estoque local",
            description=(
                "Alinhar a proposta ao calendário de lançamentos ou estoque de imóveis da "
                "região — o momento certo pesa mais que o canal escolhido."
            ),
            priority=priority_from_score(score),
            confidence=score.urgency_score,
            reason="Mercado imobiliário tem janelas de decisão curtas e sazonais.",
        )
