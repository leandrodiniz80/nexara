from decimal import Decimal

from pydantic import BaseModel


class MissionWorkspaceMetrics(BaseModel):
    """A read-only snapshot of a Mission's numbers for display — every field is
    either read straight off the persisted MissionMetrics row or counted from
    already-persisted OutreachAssets. Nothing here is recomputed: if MissionMetrics
    hasn't been refreshed recently, these numbers are exactly as stale as it is.

    `estimated_revenue` is `MissionMetrics.won_value` only (closed-won value) — not
    the weighted open-pipeline forecast `MissionEngine.summary()` computes, since
    that computation is exactly the kind of recalculation this layer is not allowed
    to do. Call that method directly for a forecast.
    """

    companies_found: int
    qualified: int
    prospects: int
    assets_generated: int
    assets_pending: int
    meetings: int
    contracts: int
    conversion_rate: float | None = None
    estimated_revenue: Decimal
