from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SalesKPI(BaseModel):
    """One standardized executive indicator — frozen: a KPI is never edited
    after being generated, only ever regenerated fresh from the
    ExecutiveSalesDashboard that produced it. `value` is a float for
    numeric indicators (percentages, currency) and a str for textual ones
    (e.g. a health tier or a trend direction) — SalesKPIService never
    invents a number for something that is inherently a label.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    value: float | str
    unit: str
    status: str
    description: str
    generated_at: datetime
