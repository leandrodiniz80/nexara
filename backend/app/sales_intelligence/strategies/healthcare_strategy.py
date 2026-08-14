from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class HealthcareStrategy(SalesStrategyBase):
    """Healthcare is trust-driven and slower to close — relationship_score weighted highest."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.HEALTHCARE
    _weights: ClassVar[dict[str, float]] = {
        "company_score": 0.25,
        "potential_score": 0.20,
        "urgency_score": 0.10,
        "visibility_score": 0.15,
        "relationship_score": 0.30,
    }

    def _flavor_recommendation(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> Recommendation:
        return Recommendation(
            title="Priorizar construção de confiança antes da oferta",
            description=(
                "Abrir com conteúdo de autoridade/credibilidade antes de qualquer proposta "
                "comercial — decisões em saúde raramente são feitas no primeiro contato."
            ),
            priority=priority_from_score(score),
            confidence=score.relationship_score,
            reason="Setor de saúde exige abordagem consultiva e ciclo de decisão mais longo.",
        )
