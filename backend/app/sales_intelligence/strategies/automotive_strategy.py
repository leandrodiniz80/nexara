from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class AutomotiveStrategy(SalesStrategyBase):
    """High-ticket, size-sensitive vertical — company_score weighted highest."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.AUTOMOTIVE
    _weights: ClassVar[dict[str, float]] = {
        "company_score": 0.35,
        "potential_score": 0.20,
        "urgency_score": 0.15,
        "visibility_score": 0.15,
        "relationship_score": 0.15,
    }

    def _flavor_recommendation(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> Recommendation:
        return Recommendation(
            title="Destacar diferenciação frente à concorrência direta",
            description=(
                "Posicionar a proposta contra concessionárias/revendas concorrentes no "
                "mesmo raio de atuação, não apenas contra o silêncio do mercado."
            ),
            priority=priority_from_score(score),
            confidence=score.company_score,
            reason="Automotivo é um mercado de ticket alto e concorrência direta visível.",
        )
