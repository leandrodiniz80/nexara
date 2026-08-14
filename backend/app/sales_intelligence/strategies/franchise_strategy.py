from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class FranchiseStrategy(SalesStrategyBase):
    """Franchises are about multi-unit scale — company_score weighted highest."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.FRANCHISE
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
            title="Avaliar proposta multi-unidade padronizada",
            description=(
                "Estruturar a oferta considerando replicação entre todas as unidades da "
                "rede, com padrão de marca único, em vez de negociar unidade a unidade."
            ),
            priority=priority_from_score(score),
            confidence=score.company_score,
            reason="Franquias decidem em escala — o ganho está no contrato multi-unidade.",
        )
