import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class CRMContact(BaseModel):
    """A person at a CRMCompany. `company_id` is a bare reference, never the full
    CRMCompany embedded — the same "reference by id" convention every module in
    this platform already uses.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    company_id: uuid.UUID
    name: str
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
