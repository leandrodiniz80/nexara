from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SalesPlaybook(BaseModel):
    """A recommended commercial strategy for one opportunity — which cadence
    to use, at what priority, and through which channels. A frozen snapshot:
    SalesPlaybookService always produces a fresh SalesPlaybook rather than
    mutating one in place, the same "definition is immutable" convention as
    CRMStage/SalesCadenceStep.

    `cadence_name` is a plain recommendation string — it names which cadence
    a caller *should* use, but this module does not call SalesCadenceService
    itself, and today only "Cadência Comercial Padrão" actually exists as a
    built cadence. Wiring a name to a real cadence builder is future
    integration work, not this sprint's.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    target_segment: str
    company_size: str
    priority: str
    cadence_name: str
    estimated_duration: int
    recommended_channels: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
