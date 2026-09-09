import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.leads.lead import LeadResponse

FailureState = Literal["on_track", "at_risk", "failing"]


class WorkdayNextResponse(BaseModel):
    """GET /workday/next. lead is None only when there's nothing left to
    work on (empty queue) — the frontend shows a "caught up" state instead
    of opening a modal. is_new_focus distinguishes a freshly-picked lead
    from an idempotent re-return of whichever lead the caller already had
    in focus (calling this endpoint again mid-session never advances past
    an unfinished lead — see get_workday_next()'s own docstring)."""

    lead: LeadResponse | None
    is_new_focus: bool
    tasks_completed_today: int
    streak_days: int


class WorkdaySummaryResponse(BaseModel):
    """GET /workday/summary — the "what does today look like" snapshot the
    Command Center reads on load. focus_message is a ready-to-render
    sentence built server-side (_build_focus_message() in workday.py), same
    "backend writes the sentence" rule the timeline/activity feed already
    follow."""

    today_tasks: int
    overdue_tasks: int
    high_priority_leads: int
    leads_at_risk: int
    estimated_revenue_at_risk: float
    focus_message: str
    # Revenue-intelligence round, both additive. revenue_at_risk is a
    # narrower, probability-weighted figure than estimated_revenue_at_risk
    # above: contacted leads that are overdue OR stale (vs. that field's
    # contacted+stale-only), summed by expected_value (vs. raw estimated
    # value) — "money genuinely at risk, probability-adjusted" rather than
    # "money attached to leads going cold." today_potential_revenue is the
    # Command Center's "Hoje você pode gerar R$ X": expected_value summed
    # over today's actionable leads (overdue + due today).
    revenue_at_risk: int = 0
    today_potential_revenue: int = 0
    # AI Deal Coach round, all additive/derived at read time from the same
    # already-scored `ranked` list this endpoint already computes — zero new
    # queries. money_in_play_today is the same figure as
    # today_potential_revenue above, just re-exposed under the Deal Coach's
    # own vocabulary (expected_value summed over today's actionable leads);
    # money_at_risk_today narrows that further to only deal_risk_level ==
    # "critical" leads (compute_deal_risk, scoring.py); critical_deals_count
    # is how many of those there are.
    money_in_play_today: int = 0
    money_at_risk_today: int = 0
    critical_deals_count: int = 0
    # Execution-assistance round, widened by the Autonomous-sales-OS
    # round's auto_execute_engine() (execution_engine.py) — how many leads
    # were auto-sent a message or auto-booked a meeting today, gated behind
    # settings.AUTO_MODE_ENABLED (always 0 while that's off, which is the
    # default). Counted via its own distinct UserNotification message
    # prefix, not LeadActivityLog's "message_sent" entries — those also
    # include a manual "Enviar agora" click (POST /leads/{id}/execute-action),
    # which this field deliberately excludes: "auto" means auto.
    auto_actions_executed_today: int = 0
    # Feedback-loop-of-outcomes round — the Command Center's "X% das suas
    # mensagens recebem resposta": compute_response_metrics()'s own 30-day
    # response_rate (scoring.py), reused as-is rather than a second,
    # today-only figure — a single day of sends is too small a sample to
    # headline with (see WorkdayPerformanceResponse.response_rate_today
    # below for the sharper, noisier daily number the Performance Panel
    # shows instead).
    response_rate: float = 0.0
    # Sales-operating-system round, all reused from the same already-scored
    # `ranked` list this endpoint already computes (see
    # _compute_response_and_pipeline_pressure() in workday.py) — zero new
    # queries. pending_responses_count/high_value_at_risk_count both read
    # score_leads()'s own has_pending_response/expected_value/deal_risk_level
    # fields; pipeline_expected_value sums expected_value across every
    # non-converted lead in that same candidate pool — an approximation at
    # very large org scale, same one high_priority_leads/revenue_at_risk
    # above already accept (see rank_leads_by_priority's own candidate-pool
    # docstring, scoring.py).
    pending_responses_count: int = 0
    high_value_at_risk_count: int = 0
    pipeline_expected_value: int = 0
    # Execution-engine round — the Command Center's "Próxima ação
    # obrigatória": get_next_mandatory_lead() (workday_engine.py) applied to
    # this same endpoint's already-computed `ranked` list run through
    # build_action_queue() first, zero new queries. None only when the
    # action queue itself is empty (nothing next_best_action_type-eligible
    # and non-converted/non-lost) — the frontend hides the section instead
    # of rendering a null lead.
    next_mandatory_lead_id: uuid.UUID | None = None
    # Revenue-loop round — the Command Center's "O que mais gera dinheiro
    # hoje": the single highest-earning bucket in each of
    # compute_revenue_attribution()'s three breakdowns (scoring.py),
    # reduced from a full dict to just its winner via top_revenue_bucket()
    # — this endpoint needs one headline answer per dimension, not the
    # full numbers (see RevenueSummaryResponse.revenue_by_action for the
    # full call/message/meeting breakdown instead). All three are None
    # until at least one lead has actually converted with real attributed
    # revenue behind it, same "no signal yet" rule this codebase's other
    # learned fields already follow.
    top_revenue_action: str | None = None
    top_revenue_industry: str | None = None
    top_revenue_company_size: str | None = None


class EnforcementStateResponse(BaseModel):
    """GET /workday/enforcement-state — Autonomous-sales-OS round's hard
    block: when blocked=true, the frontend shows a fullscreen overlay the
    user cannot dismiss except by executing required_action on lead_id.
    Reuses get_next_mandatory_lead() (workday_engine.py) — the exact same
    lead WorkdaySummaryResponse.next_mandatory_lead_id already points at,
    exposed here as an actual gate (with enough lead detail to render
    without a second fetch) rather than a dismissible Command Center card.

    required_action is always one of send_message/call_now/schedule_meeting
    — the three POST /leads/{id}/execute-action already accepts — even
    when the mandatory lead's own next_best_action_type is "monitor" (its
    only other possible value here, since get_next_mandatory_lead() never
    selects a converted/lost lead): that only happens when the trigger was
    a pending response on an otherwise low-risk lead, in which case this
    falls back to send_message — a message still awaiting reply is,
    definitionally, something to respond to."""

    blocked: bool
    lead_id: uuid.UUID | None = None
    name: str | None = None
    company_name: str | None = None
    phone: str | None = None
    expected_value: int | None = None
    required_action: str | None = None
    next_best_action: str | None = None
    reason: str | None = None


class ActionQueueItem(BaseModel):
    """GET /workday/action-queue's own per-item shape — a deliberately
    narrow projection of LeadResponse (build_action_queue(), workday_engine.py)
    rather than the full lead payload: this endpoint's whole point is a
    short, scannable "what to do next" list, not another full lead fetch.
    The frontend opens the full lead modal via lead_id when "Botão direto"
    is clicked (reusing whatever full Lead objects it already has cached),
    rather than this endpoint carrying the full record itself."""

    lead_id: uuid.UUID
    name: str
    deal_risk_level: str | None
    expected_value: int
    next_best_action: str | None
    next_best_action_type: str | None
    next_best_action_urgency: str | None


class WorkdayCompleteAndNextRequest(BaseModel):
    lead_id: uuid.UUID


class WorkdayCompleteAndNextResponse(BaseModel):
    """POST /workday/complete-and-next. next_lead is None once the queue is
    empty — same "caught up" signal as WorkdayNextResponse.lead — so the
    frontend can end the flow instead of trying to open a null lead.
    completed_lead carries the just-completed lead's fresh state (cleared
    next_action, updated score) alongside completed_lead_id, so the
    frontend can patch its local caches the same way POST
    /leads/{id}/complete-task's response already lets it."""

    completed_lead_id: uuid.UUID
    completed_lead: LeadResponse
    next_lead: LeadResponse | None


class WorkdayPerformanceResponse(BaseModel):
    """GET /workday/performance — the accountability layer's own snapshot:
    how much of today's expected work actually got done, what yesterday's
    neglect is now costing, and the streak. failure_state/
    accountability_message are additive beyond the original spec's literal
    field list — the Performance Panel needs both to render its message and
    color, and there's no other endpoint that already carries them."""

    tasks_completed_today: int
    tasks_expected_today: int
    completion_rate: float
    overdue_tasks: int
    leads_ignored_yesterday: int
    estimated_revenue_lost: float
    streak_days: int
    failure_state: FailureState
    accountability_message: str
    # Same probability-weighted "contacted + (overdue or stale)" figure as
    # WorkdaySummaryResponse.revenue_at_risk above — additive.
    revenue_at_risk: int = 0
    # AI Deal Coach round. critical_deals is the same deal_risk_level ==
    # "critical" count as WorkdaySummaryResponse.critical_deals_count, reused
    # from this endpoint's own already-computed `ranked` list. money_saved_today
    # is a proxy, not an exact figure: the exact deal_risk_level a now-
    # completed lead had *before* its task was finished isn't recoverable at
    # read time (completing it clears next_action_due_at/bumps updated_at, so
    # recomputing risk now would show "low") — so this sums estimated_value
    # for leads with a task_completed activity today whose estimated_value
    # clears HIGH_VALUE_LEAD_THRESHOLD, as a stand-in for "high-value deals
    # that got acted on today instead of going cold."
    critical_deals: int = 0
    money_saved_today: float = 0
    # Same auto-send-only count as WorkdaySummaryResponse.auto_actions_executed_today
    # above — the Performance Panel's own "ações automatizadas hoje".
    auto_actions_executed_today: int = 0
    # Feedback-loop-of-outcomes round — today-only counterpart to
    # WorkdaySummaryResponse.response_rate above (that one's a steadier
    # 30-day figure for the Command Center's headline; these are the day's
    # own raw numbers for the accountability layer).
    response_rate_today: float = 0.0
    responses_received_today: int = 0
    # Sales-operating-system round — from the same today-scoped response
    # rows responses_received_today above already reads
    # (_compute_response_metrics_today, workday.py), no new query.
    # avg_response_time_today is None (not 0.0) when nobody responded
    # today at all, same "None until there's real signal" rule
    # compute_response_metrics()'s own avg_response_time_minutes follows.
    avg_response_time_today: float | None = None
    fast_responses_today: int = 0
    # Revenue-loop round. revenue_generated_today sums estimated_value for
    # every lead with a "lead_won" LeadActivityLog entry (the precise
    # conversion-moment marker PATCH /leads/{id}/status writes) created
    # today — the accountability layer's own "here's the money you actually
    # closed today," distinct from money_saved_today above (a proxy for
    # deals worked on, not deals won). avg_revenue_per_conversion is the
    # all-time mean estimated_value across every converted lead this org
    # has ever had (not today-scoped, same "steadier, not noisy" rationale
    # response_rate/avg_time_to_close_days already follow elsewhere) — None
    # until at least one lead has ever converted.
    revenue_generated_today: float = 0.0
    avg_revenue_per_conversion: float | None = None


class WorkdayTargetResponse(BaseModel):
    """GET /workday/target — the daily gamification target. daily_target is
    a fixed default for now (no per-user/org customization yet); completed_
    today reuses the same tasks_completed_today _workday_stats() already
    computes for GET /workday/next and .../performance.

    Autonomous-sales-OS round adds a second, revenue-based target
    alongside the original task-count one above — additive, not a
    replacement (the prompt's own literal ask was to "replace" the logic,
    but this endpoint already ships and nothing else in this codebase
    reads task-based daily_target/remaining/progress as dead weight, so
    dropping them would violate this same round's own "never break
    existing endpoints" rule; the three new fields below are the actual
    revenue-based target, additive on top). daily_target_revenue is the
    average converted revenue over the last 7 days (0.0/None-safe — see
    get_workday_target()'s own docstring for the exact query);
    current_expected reuses the same expected_value-summed-over-today's-
    actionable-leads figure WorkdaySummaryResponse.today_potential_revenue
    already computes; gap is simply the difference, positive when behind
    target."""

    daily_target: int
    completed_today: int
    remaining: int
    progress: float
    daily_target_revenue: float = 0.0
    current_expected: int = 0
    gap: float = 0.0
