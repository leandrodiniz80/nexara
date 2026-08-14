from pydantic import BaseModel, Field

from app.crm.models.crm_activity import CRMActivity
from app.crm.models.crm_opportunity import CRMOpportunity


class OpportunityLifecycleResult(BaseModel):
    """What every OpportunityLifecycleService method returns — the same
    "always a result, never a raised exception past this boundary" shape as
    every other *Result type in this codebase. `activity` is only populated
    by schedule_activity(); every other operation leaves it None.
    """

    success: bool
    opportunity: CRMOpportunity | None = None
    activity: CRMActivity | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_time: float
