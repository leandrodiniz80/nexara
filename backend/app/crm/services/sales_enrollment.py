import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution import (
    SalesCadenceExecution,
    SalesCadenceExecutionStatus,
)
from app.crm.services.sales_playbook import SalesPlaybook


class SalesEnrollment(BaseModel):
    """Represents that one CRMOpportunity has entered one SalesCadence
    through one SalesPlaybook — the missing link between "which playbook",
    "which cadence" and "how far along its execution is". A frozen
    aggregator: it never replaces which opportunity/playbook/cadence/
    execution it points to, though the wrapped SalesCadenceExecution itself
    remains the same mutable instance SalesCadenceExecutionService keeps
    advancing — this type just fixes the *link* between the four, not their
    own internal state.

    Nothing here is persisted; this is purely an in-memory domain
    aggregate for as long as its caller holds a reference to it.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    opportunity: CRMOpportunity
    playbook: SalesPlaybook
    cadence: SalesCadence
    execution: SalesCadenceExecution
    started_at: datetime | None = None
    status: SalesCadenceExecutionStatus = SalesCadenceExecutionStatus.NOT_STARTED
    metadata: dict[str, Any] = Field(default_factory=dict)
