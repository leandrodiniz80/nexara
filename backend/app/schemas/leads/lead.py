import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    name: str
    email: str
    phone: str = ""


class LeadUpdateStatus(BaseModel):
    status: str = Field(pattern="^(new|contacted|converted|lost)$")


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: str
    name: str
    email: str
    phone: str
    status: str
    score: int
    notes: str | None = None
    next_action: str | None = None
    next_action_due_at: datetime | None = None
    owner_email: str | None = None
    created_at: datetime
    updated_at: datetime


class LeadStatusUpdateResponse(BaseModel):
    """PATCH /leads/{id}/status returns both the updated lead and any
    automation "notify" messages that fired — the backend has no channel of
    its own to show a toast on, so the frontend renders these from here."""

    lead: LeadResponse
    notifications: list[str] = Field(default_factory=list)


class LeadCreateResponse(BaseModel):
    """Same rationale as LeadStatusUpdateResponse — POST /leads can now also
    fire a "lead_created" automation (e.g. a notify), so its response needs
    the same {lead, notifications} shape."""

    lead: LeadResponse
    notifications: list[str] = Field(default_factory=list)


class LeadListResponse(BaseModel):
    """Opt-in shape for GET /leads?with_meta=true — the default (no query
    param) response stays the plain list[LeadResponse] it's always been.
    Structurally unambiguous from a bare list, so response_model can be a
    plain Union with no discriminator."""

    data: list[LeadResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class LeadMetricsByStatus(BaseModel):
    new: int
    contacted: int
    converted: int


class LeadMetricsResponse(BaseModel):
    total: int
    by_status: LeadMetricsByStatus
    conversion_rate: float
    avg_score: float


class UpdateLeadDetailsRequest(BaseModel):
    """PATCH /leads/{id}/details — every field optional, applied via
    exclude_unset so autosave-on-blur can PATCH one field (e.g. just notes)
    without clobbering the other two."""

    notes: str | None = None
    next_action: str | None = None
    next_action_due_at: datetime | None = None


class UpdateLeadOwnerRequest(BaseModel):
    """PATCH /leads/{id}/owner. owner_email is a required key but its value
    may be null — an explicit "unassign" — the router validates membership
    only when it's non-null."""

    owner_email: str | None


class LeadTimelineEntry(BaseModel):
    """GET /leads/{id}/timeline entry. "from" is a Python keyword, so the
    field is named from_ internally — populate_by_name lets callers construct
    it as from_=... while FastAPI's response serialization (response_model_by_alias
    defaults to True) still emits the wire key as "from"."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    from_: str | None = Field(default=None, alias="from")
    to: str
    created_at: datetime
