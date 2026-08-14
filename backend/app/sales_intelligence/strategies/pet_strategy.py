from typing import ClassVar

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.recommendations.recommendation_engine import priority_from_score
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase


class PetStrategy(SalesStrategyBase):
    """Pet is a heavily visual, social-first vertical — visibility_score weighted highest."""

    segment: ClassVar[CommercialSegment] = CommercialSegment.PET
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
            title="Priorizar canais visuais e redes sociais",
            description=(
                "Enfatizar conteúdo de fotos/vídeos de pets e presença em redes sociais — "
                "o segmento responde fortemente a esse tipo de conteúdo na decisão de compra."
            ),
            priority=priority_from_score(score),
            confidence=score.visibility_score,
            reason="Pet é um dos segmentos mais social-media-driven do varejo local.",
        )
