import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class CRMCompany(BaseModel):
    """A company as known to the CRM — deliberately its own record, not a reference
    to app.schemas.prospecting.company.CompanyRead: the CRM module is self-contained
    and knows nothing about Prospect/Research.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    segment: str | None = None
    city: str | None = None
    state: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
