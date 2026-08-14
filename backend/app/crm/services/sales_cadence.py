from datetime import date

from pydantic import BaseModel, Field

from app.crm.services.sales_cadence_step import SalesCadenceStep


class SalesCadence(BaseModel):
    """What SalesCadenceService.build_cadence() returns — the platform's
    standard 5-step prospecting cadence, plus where a given opportunity
    currently stands within it. Nothing here is persisted or scheduled; a
    non-empty `errors` list is this type's own failure signal (there is no
    separate `success` field).
    """

    steps: list[SalesCadenceStep] = Field(default_factory=list)
    total_steps: int = 0
    estimated_duration: int | None = None
    current_step: SalesCadenceStep | None = None
    next_step: SalesCadenceStep | None = None
    recommended_finish_date: date | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
