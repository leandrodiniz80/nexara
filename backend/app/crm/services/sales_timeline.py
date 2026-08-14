from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_enrollment import SalesEnrollment
from app.crm.services.sales_timeline_event import SalesTimelineEvent


class SalesTimeline(BaseModel):
    """The full chronological history of one SalesEnrollment's execution —
    frozen: SalesTimelineService never edits a SalesTimeline in place, it
    always returns a new one with one more event appended to the end of the
    previous, unedited list.
    """

    model_config = ConfigDict(frozen=True)

    enrollment: SalesEnrollment
    events: list[SalesTimelineEvent] = Field(default_factory=list)
    created_at: datetime
    last_updated: datetime
