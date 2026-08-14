from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SalesReportSection(BaseModel):
    """One labeled group of already-computed values inside a SalesReport —
    frozen: a section is never edited after being built, only ever
    regenerated fresh from the ExecutiveSalesDashboard/SalesKPICatalog that
    produced it. `items` holds each value under its own label exactly as
    copied from the source object — this type performs no calculation of
    its own.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    items: dict[str, Any] = Field(default_factory=dict)
