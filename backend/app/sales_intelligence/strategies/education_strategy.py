from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class EducationStrategy(SalesStrategyBase):
    """Enrollment cycles are long and relationship/content-driven — potential_score
    and relationship_score weighted highest."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.EDUCATION
    _weights: ClassVar[dict[str, float]] = {
        "company_score": 0.20,
        "potential_score": 0.30,
        "urgency_score": 0.10,
        "visibility_score": 0.15,
        "relationship_score": 0.25,
    }

    def _flavor_recommendation(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> Recommendation:
        return Recommendation(
            title="Construir relacionamento ao longo do calendário letivo",
            description=(
                "Manter presença contínua entre ciclos de matrícula em vez de concentrar "
                "esforço apenas no pico de captação."
            ),
            priority=priority_from_score(score),
            confidence=score.potential_score,
            reason="Educação tem ciclo de decisão longo, atrelado ao calendário acadêmico.",
        )
