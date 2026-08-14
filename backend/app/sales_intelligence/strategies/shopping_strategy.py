from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class ShoppingStrategy(SalesStrategyBase):
    """Shopping centers sell on foot traffic — visibility_score weighted highest.
    Also the segment named in the module's own rule example (segment == "Shopping" ->
    +20 to company_score), which fires for every profile this strategy handles."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.SHOPPING
    _weights: ClassVar[dict[str, float]] = {
        "company_score": 0.20,
        "potential_score": 0.15,
        "urgency_score": 0.15,
        "visibility_score": 0.35,
        "relationship_score": 0.15,
    }

    def _flavor_recommendation(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> Recommendation:
        return Recommendation(
            title="Explorar o fluxo de visitantes do shopping na proposta",
            description=(
                "Usar o volume de circulação do shopping como argumento central — é o "
                "principal ativo comercial deste segmento."
            ),
            priority=priority_from_score(score),
            confidence=score.visibility_score,
            reason="Shoppings vendem exposição a fluxo, não relacionamento individual.",
        )
