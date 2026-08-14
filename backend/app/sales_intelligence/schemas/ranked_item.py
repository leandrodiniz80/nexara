from typing import Any

from pydantic import BaseModel, ConfigDict

from app.sales_intelligence.models.commercial_score import CommercialScore


class RankedItem(BaseModel):
    """One entry going into/out of RankingEngine. `reference` is deliberately opaque
    (a company id, a prospect id, a campaign id, or anything else) — this module never
    interprets it, only carries it alongside the score it was ranked by. That's what
    lets rank_companies()/rank_prospects()/rank_campaigns() share one implementation
    without this module needing to know what a Company/Prospect/Campaign is.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    reference: Any
    score: CommercialScore
