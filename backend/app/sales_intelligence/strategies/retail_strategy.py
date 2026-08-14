from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class RetailStrategy(SalesStrategyBase):
    """Retail conversion leans on discoverability — visibility_score weighted highest."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.RETAIL
    _weights: ClassVar[dict[str, float]] = {
        "company_score": 0.20,
        "potential_score": 0.20,
        "urgency_score": 0.15,
        "visibility_score": 0.30,
        "relationship_score": 0.15,
    }

    def _flavor_recommendation(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> Recommendation:
        return Recommendation(
            title="Reforçar presença visual no ponto de venda",
            description=(
                "Priorizar mídia visível na fachada/vitrine e no entorno imediato do "
                "ponto de venda, além do digital."
            ),
            priority=priority_from_score(score),
            confidence=score.visibility_score,
            reason=(
                "Varejo converte principalmente por visibilidade e fluxo, não por "
                "relacionamento longo."
            ),
        )
