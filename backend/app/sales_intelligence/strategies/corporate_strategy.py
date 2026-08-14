from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class CorporateStrategy(SalesStrategyBase):
    """B2B corporate sales are slow and relationship-heavy — relationship_score and
    company_score weighted highest, urgency deliberately weighted low."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.CORPORATE
    _weights: ClassVar[dict[str, float]] = {
        "company_score": 0.30,
        "potential_score": 0.20,
        "urgency_score": 0.10,
        "visibility_score": 0.10,
        "relationship_score": 0.30,
    }

    def _flavor_recommendation(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> Recommendation:
        return Recommendation(
            title="Estruturar ciclo de vendas B2B com múltiplos contatos",
            description=(
                "Planejar uma sequência de pontos de contato (institucional, técnico, "
                "decisor) antes de uma proposta comercial formal."
            ),
            priority=priority_from_score(score),
            confidence=score.relationship_score,
            reason="Vendas corporativas raramente fecham num único contato direto.",
        )
