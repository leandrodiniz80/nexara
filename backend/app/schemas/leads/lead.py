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
    # Only meaningful on a transition to "lost" (why it was lost) — the
    # frontend's dedicated "Mark as lost" flow always sends one of a fixed
    # set of options ("Preço alto"/"Sem resposta"/"Sem interesse"/"Timing"),
    # but this stays a plain string rather than a Literal so a future reason
    # doesn't require a schema change. Ignored for every other status.
    reason: str | None = None


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
    # Derived from next_action_due_at at read time (score_leads), same
    # pattern as score/score_breakdown — never stored, so nothing to
    # migrate. days_overdue is None whenever is_overdue is False.
    is_overdue: bool = False
    days_overdue: int | None = None
    # Rule-based (no LLM) — see compute_next_best_action() in scoring.py.
    # None for converted/lost leads, where there's nothing left to act on.
    next_best_action: str | None = None
    # Only populated when next_best_action is set AND AI_ENABLED — one
    # template per next_best_action case (generate_lead_message_by_action()
    # in enrichment.py), not the single first-contact-only template POST
    # /leads/{id}/generate-message uses; no extra LLM/API call either way.
    suggested_message: str | None = None
    # Revenue-intelligence layer — all three computed at read time
    # (compute_win_probability/get_lead_estimated_value, scoring.py), same
    # "never persisted" pattern as score/is_overdue. estimated_value and
    # expected_value are ints rather than this codebase's usual float money
    # fields: both are always exact whole numbers given today's discrete
    # company-size buckets (1000/5000/20000) and integer win_probability, so
    # int loses nothing and matches win_probability's own type.
    win_probability: int = 0
    estimated_value: int = 0
    expected_value: int = 0
    # Learning-layer explainability (feedback-loop round) — one ready-to-
    # render sentence built by build_priority_reason() (scoring.py) from the
    # same signals already driving score/win_probability/next_best_action,
    # same "the backend writes the sentence" rule as focus_message/
    # accountability_message. Always populated by score_leads(), never
    # empty — even a quiet lead gets a neutral sentence.
    priority_reason: str = ""
    # AI Deal Coach round — deterministic, no external AI calls: risk_level
    # collapses expected_value/win_probability/activity recency into one
    # "how worried should I be" bucket (compute_deal_risk, scoring.py),
    # deal_risk_reason a short one-line explanation. Both populated by
    # score_leads() the same way score/win_probability already are.
    deal_risk_level: str | None = None
    deal_risk_reason: str | None = None
    # Coarse, machine-readable action recommendation driven by
    # deal_risk_level (compute_action_type_and_urgency, scoring.py) —
    # distinct from next_best_action above (a full sentence from an older,
    # separate rule table): "call_now"/"send_message"/"schedule_meeting"/
    # "drop_lead"/"monitor", paired with an urgency tag, meant for the
    # frontend to badge/button on directly (LeadCard) without string-
    # matching next_best_action's prose. None only for converted leads.
    next_best_action_type: str | None = None
    next_best_action_urgency: str | None = None
    # Execution-assistance round — the "just do it for me" gate: true only
    # when next_best_action_type == "send_message" AND suggested_message is
    # actually populated, in which case ready_to_send_message mirrors
    # suggested_message so the frontend's "Enviar agora" button (and
    # POST /leads/{id}/execute-action) don't have to re-derive the same two-
    # field check themselves. False/None otherwise — never a stale or
    # partially-stale value.
    ready_to_send_message: str | None = None
    auto_action_available: bool = False
    # Feedback-loop-of-outcomes round — derived from LeadActivityLog's
    # "lead_responded"/"lead_interested"/"lead_rejected" entries (see
    # POST /leads/{id}/record-response), not a stored column: no migration,
    # same "encode it in the log, derive it at read time" adaptation
    # LOSS_REASON_MARKER (scoring.py) already established. "no_response" is
    # a real, always-populated value here — not a stand-in for null — for
    # a lead with no response recorded yet. response_time_minutes is only
    # non-null once a response exists, timed from that lead's most recent
    # "message_sent" entry.
    lead_response_state: str = "no_response"
    response_time_minutes: int | None = None
    # Sales-operating-system round — the "did they ever reply to what we
    # last sent" pair, derived from the same LeadActivityLog rows as
    # lead_response_state above but comparing timestamps directly rather
    # than reading the latest response's own state: has_pending_response is
    # true whenever a "message_sent" entry exists with no response-type
    # entry after it (so it stays true across a stale old response and a
    # newer unanswered message — see score_leads()'s own docstring).
    # response_delay_minutes is minutes since that lead's most recent
    # "message_sent", populated whenever one exists at all (pending or
    # not) — distinct from response_time_minutes above, which is only ever
    # set once a response actually landed.
    has_pending_response: bool = False
    response_delay_minutes: int | None = None
    # Sales-operating-system round — days since this lead's most recent
    # LeadActivityLog entry of any kind, not to be confused with the
    # existing days_idle concept several score_breakdown lines already use
    # internally (derived from the stored updated_at column): some
    # activity — e.g. POST /leads/{id}/record-response — logs to the
    # timeline without mutating any Lead column, so updated_at can lag
    # behind what actually last happened on this lead. Falls back to the
    # updated_at-based figure on a lead with no logged activity at all.
    days_since_last_activity: int = 0
    in_focus: bool = False
    company_name: str | None = None
    website: str | None = None
    enrichment_data: EnrichmentData | None = None
    created_at: datetime
    updated_at: datetime
    # Revenue-maximization round — Opportunity Cost Engine (Task 1):
    # this org's single highest expected_value among the batch score_leads()
    # last scored this lead alongside, minus this lead's own expected_value.
    # Always >= 0 (the highest-value lead's own opportunity_cost is 0
    # against itself). Powers LeadCard's own "⚠️ Perdendo R$ X" badge.
    opportunity_cost: int = 0
    # Revenue Acceleration Mode (Task 3) — a global, org-wide flag (see
    # compute_acceleration_mode(), scoring.py), uniform across every
    # LeadResponse in the same score_leads() batch, not a genuine per-lead
    # attribute. Exposed here so a caller already holding an already-scored
    # list (e.g. auto_execute_engine(), execution_engine.py) can read the
    # same global state score_leads() already computed without a second,
    # redundant DB round-trip.
    acceleration_mode: bool = False


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


class ExecuteLeadActionRequest(BaseModel):
    """POST /leads/{id}/execute-action — execution-assistance round. A
    Literal (not the free-string pattern LeadUpdateStatus.reason uses)
    since these three are the entire, fixed vocabulary
    compute_action_type_and_urgency() (scoring.py) ever produces; a
    request for anything else is a client bug, not a future-proofing
    concern worth a plain string for."""

    action: Literal["send_message", "call_now", "schedule_meeting"]


class RecordLeadResponseRequest(BaseModel):
    """POST /leads/{id}/record-response — feedback-loop-of-outcomes round.
    A Literal for the same reason ExecuteLeadActionRequest.action is one:
    this is the entire fixed vocabulary lead_response_state
    (score_leads()/scoring.py) ever derives from it."""

    response: Literal["responded", "interested", "not_interested"]


class ActionEffectivenessResponse(BaseModel):
    """compute_action_effectiveness() (scoring.py) — org-wide "did this
    ACTION lead to a RESULT" per action type (call_now/send_message/
    schedule_meeting), inferred from LeadActivityLog's action_call/
    action_message/action_meeting entries (execute_lead_action(),
    execution_engine.py) against lead_interested/converted outcomes — no
    FK, no ML. Feeds compute_lead_score()'s own "learned channel" bonus.
    Each rate is None (not 0.0) until at least one lead has had that
    action type at all, same "None until there's real signal" rule
    ConversionInsightsResponse's own fields already follow."""

    call_success_rate: float | None = None
    message_success_rate: float | None = None
    meeting_success_rate: float | None = None


class RevenueAttributionResponse(BaseModel):
    """compute_revenue_attribution() (scoring.py) — "what actually generated
    the money," a step beyond ActionEffectivenessResponse's own "what's
    likely to work" success-rate view. For each converted lead, the LAST
    action_call/action_message/action_meeting event logged before that
    lead's own conversion (approximated by its updated_at — no separate
    converted_at column, same "known approximation" spirit
    compute_action_effectiveness() already discloses) is credited with the
    lead's *entire* estimated_value — no partial split across several
    actions, no ML. revenue_by_action's three keys always exist (0.0
    default, not absent) since "no revenue from calls yet" is itself a
    useful, real answer; revenue_by_industry/revenue_by_company_size only
    carry keys that actually have at least one converted lead behind them.

    Winner Pattern Replication (Task 4, revenue-maximization round) adds
    top_combination: the single "action | industry | company_size" string
    (e.g. "call | Technology | 500+") with the most attributed revenue
    behind it — None until at least one converted lead has both a
    qualifying action link and enrichment_data at once, same "no signal
    yet" rule this codebase's other learned fields already follow."""

    revenue_by_action: dict[str, float] = Field(
        default_factory=lambda: {"call": 0.0, "message": 0.0, "meeting": 0.0}
    )
    revenue_by_industry: dict[str, float] = Field(default_factory=dict)
    revenue_by_company_size: dict[str, float] = Field(default_factory=dict)
    top_combination: str | None = None


class ResponseMetricsResponse(BaseModel):
    """compute_response_metrics() (scoring.py) — org-wide messaging
    effectiveness mined from the last 30 days of message_sent/lead_responded/
    lead_interested/lead_rejected activity, the same "None until there's
    real signal" rule ConversionInsightsResponse already follows.
    best_response_industry feeds compute_lead_score()'s own "Matches
    high-response segment" bonus, beyond this round's literal response_rate/
    interest_rate/avg_response_time_minutes ask — exposed here too since a
    future Learning Panel extension will want it, and it's already computed
    as part of the same pass."""

    response_rate: float = 0.0
    interest_rate: float = 0.0
    avg_response_time_minutes: float | None = None
    best_response_industry: str | None = None


class ConversionInsightsResponse(BaseModel):
    """GET /leads/insights — org-wide patterns mined from real outcomes
    (compute_conversion_insights(), scoring.py), backing the dashboard's
    Learning Panel. Every field is None until there's enough real outcome
    data to say something (e.g. no lead converted yet), rather than a
    misleading default value."""

    best_industry: str | None = None
    best_company_size: str | None = None
    avg_time_to_close_days: int | None = None
    top_loss_reason: str | None = None


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
