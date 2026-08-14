import uuid
from typing import Any

from pydantic import BaseModel, Field


class TaskContext(BaseModel):
    """Everything one ApplicationTask execution needs. Only opaque UUID references
    to Mission/Job/Prospect/Company/Workflow — never the full entities — matching the
    same "reference by id" convention every other module in this platform already
    uses (GeneratedMessage/OutreachAsset.prospect_id, AIContext's own use of a bare
    reference for cross-module ids). Anything richer a task needs (a CompanyRead, a
    CommercialProfile, a rendered template's variables, ...) travels through the
    generic `variables` bag, the same escape hatch AIContext/CopyContext already use.
    """

    mission_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    prospect_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    workflow_id: uuid.UUID | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    requested_by: uuid.UUID | None = None
