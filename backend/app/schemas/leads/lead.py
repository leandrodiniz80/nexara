import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    name: str
    email: str
    phone: str = ""


class LeadUpdateStatus(BaseModel):
    status: str = Field(pattern="^(new|contacted|converted|lost)$")


class ScoreBreakdownItem(BaseModel):
    """One factor behind a lead's dynamically-computed score — see
    app/services/leads/scoring.py::compute_lead_score. Positive impact
    boosts the score, negative lowers it."""

    reason: str
    impact: int


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: str
    name: str
    email: str
    phone: str
    status: str
    # Computed dynamically at read time (compute_lead_score), not read
    # straight off the stored column — see scoring.py for why, and for what
    # score_breakdown's entries mean. Never persisted back to the row.
    score: int
    score_breakdown: list[ScoreBreakdownItem] = Field(default_factory=list)
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
    """GET /leads/{id}/timeline entry — unified across LeadStatusHistory
    (type="status_changed", from/to populated), AutomationActivityLog
    (type="automation_fired", message populated), and LeadActivityLog
    (type="owner_changed"/"details_updated"/"task_completed", message
    populated). from_/to stay status_changed-only (unchanged shape from
    before this round); message is the new, additive field every other
    type uses. "from" is a Python keyword, so the field is named from_
    internally — populate_by_name lets callers construct it as from_=...
    while FastAPI's response serialization (response_model_by_alias
    defaults to True) still emits the wire key as "from"."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    message: str | None = None
    created_at: datetime


class LeadTaskCompleteResponse(BaseModel):
    """Same {lead, notifications} shape as LeadStatusUpdateResponse/
    LeadCreateResponse — POST /leads/{id}/complete-task fires no automation
    today, so notifications is always []; kept for response-shape
    consistency and so a future automation on this event needs no contract
    change."""

    lead: LeadResponse
    notifications: list[str] = Field(default_factory=list)


class LeadActivityFeedEntry(BaseModel):
    """GET /leads/activity entry — the org-wide counterpart to
    LeadTimelineEntry, merging the same three sources across every lead in
    the organization (not just one). Always a synthesized message (even for
    status changes), since there's no per-entry from/to distinction worth
    keeping at this broader granularity."""

    lead_id: uuid.UUID
    lead_name: str
    type: str
    message: str
    created_at: datetime
