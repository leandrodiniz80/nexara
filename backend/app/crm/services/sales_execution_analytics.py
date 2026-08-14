from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.crm.services.sales_enrollment import SalesEnrollment
from app.crm.services.sales_execution_metrics import SalesExecutionMetrics
from app.crm.services.sales_timeline import SalesTimeline


class SalesExecutionAnalytics(BaseModel):
    """A frozen bundle of the enrollment, the timeline it was measured from
    and the resulting SalesExecutionMetrics, plus when the measurement was
    taken. SalesExecutionAnalyticsService always returns a brand new one —
    it never edits a previous SalesExecutionAnalytics in place.
    """

    model_config = ConfigDict(frozen=True)

    enrollment: SalesEnrollment
    timeline: SalesTimeline
    metrics: SalesExecutionMetrics
    generated_at: datetime
