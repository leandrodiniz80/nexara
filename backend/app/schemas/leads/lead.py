import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Coarse categorization for the unified timeline/feed — lets the frontend
# pick an icon (or otherwise branch) without hardcoding every fine-grained
# `type` value. Additive alongside `type`, not a replacement: `type` keeps
# its existing, more specific values unchanged.
TimelineCategory = Literal["status_change", "automation", "activity"]


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


class EnrichmentData(BaseModel):
    """The lead "mini-dossier" — see app/services/leads/enrichment.py for
    how it's populated (simulated for now; the shape is meant to match
    whatever a real data-provider integration returns later)."""

    industry: str
    company_size: str
    city: str
    description: str
    enriched_at: datetime


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
    in_focus: bool = False
    company_name: str | None = None
    website: str | None = None
    enrichment_data: EnrichmentData | None = None
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
    (type="status_changed"), AutomationActivityLog (type="automation_fired"),
    and LeadActivityLog (type="owner_changed"/"details_updated"/
    "task_completed"/"enriched"/"message_generated"). `id` is the
    originating row's own id (unique across all three source tables, so
    it's a stable React key / click target on its own). `message` is always
    a ready-to-render sentence — the backend builds it, never the frontend
    — including for status_changed, where from_/to (unchanged shape from
    before this round, kept for whoever already reads them) are also still
    populated. `metadata` carries whatever structured extra a given `type`
    has (from_status/to_status, action_type, automation_name); None where
    nothing extra applies. "from" is a Python keyword, so the field is
    named from_ internally — populate_by_name lets callers construct it as
    from_=... while FastAPI's response serialization (response_model_by_alias
    defaults to True) still emits the wire key as "from"."""

    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    type: str
    category: TimelineCategory
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    message: str
    metadata: dict | None = None
    created_at: datetime


class LeadTaskCompleteResponse(BaseModel):
    """Same {lead, notifications} shape as LeadStatusUpdateResponse/
    LeadCreateResponse — POST /leads/{id}/complete-task fires no automation
    today, so notifications is always []; kept for response-shape
    consistency and so a future automation on this event needs no contract
    change."""

    lead: LeadResponse
    notifications: list[str] = Field(default_factory=list)


class GenerateMessageResponse(BaseModel):
    """POST /leads/{id}/generate-message — template-based today (no LLM),
    see generate_first_contact_message() in enrichment.py."""

    message: str


class LeadActivityFeedEntry(BaseModel):
    """GET /leads/activity entry — the org-wide counterpart to
    LeadTimelineEntry, merging the same three sources across every lead in
    the organization (not just one). Always a synthesized message (even for
    status changes), since there's no per-entry from/to distinction worth
    keeping at this broader granularity. Same id/category/metadata shape as
    LeadTimelineEntry — see that model's own docstring."""

    id: uuid.UUID
    lead_id: uuid.UUID
    lead_name: str
    type: str
    category: TimelineCategory
    message: str
    metadata: dict | None = None
    created_at: datetime
