from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_kpi import SalesKPI


class SalesKPICatalog(BaseModel):
    """The frozen, standardized set of executive KPIs derived from one
    ExecutiveSalesDashboard, plus its overall score copied through
    unchanged. SalesKPIService always returns a new one; it never edits a
    previous SalesKPICatalog in place.
    """

    model_config = ConfigDict(frozen=True)

    kpis: list[SalesKPI] = Field(default_factory=list)
    overall_score: float
    generated_at: datetime
