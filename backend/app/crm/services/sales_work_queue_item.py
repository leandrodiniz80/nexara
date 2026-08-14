from datetime import date

from pydantic import BaseModel

from app.crm.models.crm_opportunity import CRMOpportunity


class SalesWorkQueueItem(BaseModel):
    """One row in a SalesWorkQueue — an ActionPlan paired back with the
    CRMOpportunity it was planned for, flattened into exactly the fields a
    seller needs to see. `priority` and the rest are carried over from the
    originating ActionPlan verbatim; nothing here is recomputed.
    """

    opportunity: CRMOpportunity
    recommended_action: str
    recommended_date: date | None
    priority: str
    estimated_duration: int | None
    reason: str | None
