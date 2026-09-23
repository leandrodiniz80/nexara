from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.models.notifications.user_notification import UserNotification
from app.schemas.leads.lead import LeadResponse
from app.schemas.workday import FailureState
from app.services.leads.enrichment import HIGH_VALUE_LEAD_THRESHOLD, get_lead_estimated_value
from app.services.leads.scoring import rank_leads_by_priority

# compute_daily_target_revenue()'s own averaging window — same 7-day span
# this codebase's other "steady, not noisy" windows already use
# (compute_response_metrics's own _RESPONSE_METRICS_WINDOW_DAYS uses 30 for
# a rarer signal; a week is enough here since conversions are the much more
# frequent event being averaged). Public (moved here from workday.py's own
# router module, product-consolidation round) so GET /product/summary
# (routers/product.py) can compute the same revenue_cutoff GET
# /workday/target already does, without a router importing from another
# router.
DAILY_TARGET_REVENUE_WINDOW_DAYS = 7

# GET /workday/summary's leads_at_risk criteria — same "contacted, no recent
# touch" definition and default window as GET /leads/attention. Public
# (moved here from workday.py's own router module, product-consolidation
# round) so GET /product/summary (routers/product.py) can reuse the same
# staleness window compute_revenue_at_risk() itself is built around.
AT_RISK_STALE_AFTER_DAYS = 3

# detect_user_failure_state()'s thresholds — see its own docstring.
_FAILING_COMPLETION_RATE = 0.3
_AT_RISK_COMPLETION_RATE = 0.6
_FAILING_OVERDUE_THRESHOLD = 5

# maybe_notify_performance_alert()'s dedup window — a "failing" alert isn't
# repeated more often than this, however often the dashboard is refreshed.
_PERFORMANCE_ALERT_DEDUP_HOURS = 6
# maybe_notify_high_value_leads()'s own per-lead dedup window — same 6h
# rhythm as the org-wide performance alert above, just keyed per-lead
# instead of per-user.
_HIGH_VALUE_ALERT_DEDUP_HOURS = 6
# "High-value" for the per-lead alert below — same shared threshold
# build_priority_reason() (scoring.py) now also uses, consolidated into
# enrichment.py (feedback-loop round) instead of two separately-maintained
# copies of the same 5000.0 constant.
_HIGH_VALUE_ALERT_THRESHOLD = HIGH_VALUE_LEAD_THRESHOLD
# "No activity" for the per-lead alert — same 7-day window
# compute_win_probability's own idle penalty and compute_lead_score's "Idle
# for over a week" line already use.
_HIGH_VALUE_ALERT_IDLE_DAYS = 7
# maybe_notify_critical_deals()'s own per-lead dedup window (AI Deal Coach
# round) — same 6h rhythm as the other per-lead alert above. Shares the
# same lead_id+created_at dedup query shape (no `type` column on
# UserNotification to filter on — see that model's own docstring), so a
# lead that already got the high-value alert in the last 6h won't also get
# this one in the same window, and vice versa: by design, one lead gets at
# most one of these per-lead nudges per window, whichever fires first.
_CRITICAL_DEAL_ALERT_DEDUP_HOURS = 6

# maybe_notify_ignored_leads()'s trigger — the prompt's own number of leads
# stuck in has_pending_response with a >24h response_delay_minutes
# (scoring.py) before it's worth an org-wide nudge.
_IGNORED_LEADS_ALERT_THRESHOLD = 5
_IGNORED_LEADS_ALERT_DEDUP_HOURS = 6
# maybe_notify_pipeline_risk()'s trigger — the prompt's own number, against
# the same probability-weighted revenue_at_risk GET /workday/summary
# already computes (compute_revenue_at_risk, this module).
_PIPELINE_RISK_ALERT_THRESHOLD = 10000.0
_PIPELINE_RISK_ALERT_DEDUP_HOURS = 6

# generate_accountability_message()'s "high pressure" tier — a stricter bar
# than detect_user_failure_state()'s own "failing" thresholds (overdue > 5,
# completion_rate < 0.3): this is for the *worst* of an already-failing day,
# not failing itself, so it never introduces a 4th FailureState value (the
# frontend's failureState color-mapping stays exactly the 3 it already
# handles).
_HIGH_PRESSURE_OVERDUE_THRESHOLD = 8
_HIGH_PRESSURE_COMPLETION_RATE = 0.3

# build_action_queue()'s own cap — the prompt's own number, same rationale
# as _HIGH_PRIORITY_TOP_N (workday.py): a short, genuinely actionable list,
# not "everything sorted."
_ACTION_QUEUE_LIMIT = 10
_RISK_LEVEL_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}
# build_action_queue()'s "force to the top" bar — deliberately its own
# number, distinct from HIGH_VALUE_LEAD_THRESHOLD (5000, enrichment.py):
# that one gates "is this a big deal at all" everywhere else in this
# codebase; this one gates "big enough to jump the queue's own risk-first
# ordering," a stricter, prompt-specified bar.
_MONEY_FIRST_THRESHOLD = 10000.0
_MONEY_FIRST_TOP_SLOTS = 3
# get_next_mandatory_lead()'s own "how overdue is too overdue to keep
# waiting" bar — same magnitude as compute_lead_score's own
# _PENDING_RESPONSE_DELAY_MINUTES_LOW (scoring.py), kept as its own literal
# here rather than an import to avoid a cross-module constant dependency
# for one plain number neither module needs to share via code.
_MANDATORY_PENDING_RESPONSE_MINUTES = 60

# Revenue-loop round — maybe_notify_high_revenue_opportunity()'s own
# trigger, the prompt's own numbers: a probability-weighted deal this big,
# this likely to close, is worth a proactive nudge rather than waiting for
# the user to notice it in a list. Same 6h per-lead dedup rhythm as
# maybe_notify_high_value_leads()/maybe_notify_critical_deals() above.
_HIGH_REVENUE_OPPORTUNITY_THRESHOLD = 10000.0
_HIGH_REVENUE_OPPORTUNITY_WIN_PROBABILITY = 70
_HIGH_REVENUE_OPPORTUNITY_ALERT_DEDUP_HOURS = 6
# Elite round's "Alerta de Oportunidade Crítica (REAL)" (Task 6) — adds an
# idle-days gate this alert never had before: value + win_probability alone
# could already fire on a deal someone is actively working right now, which
# isn't really "about to lose it." Same days_since_last_activity signal
# score_leads()'s own neglect-detection bonus already reads (scoring.py).
_HIGH_REVENUE_OPPORTUNITY_IDLE_DAYS = 2

# Revenue-maximization round — maybe_notify_focus_shift()'s own trigger
# (Task 5): same opportunity_cost bar Task 1's own score penalty uses
# (scoring.py's _OPPORTUNITY_COST_THRESHOLD), and the same "touched very
# recently" window that penalty's own has_recent_manual_activity proxy
# would cover, restated here in days since this is an org-wide, once-a-
# batch check rather than a per-lead one already carrying that boolean.
_FOCUS_SHIFT_OPPORTUNITY_COST_THRESHOLD = 5000
_FOCUS_SHIFT_RECENT_ACTIVITY_DAYS = 1
_FOCUS_SHIFT_ALERT_DEDUP_HOURS = 6
# Org-wide alert marker (see IGNORED_LEADS_ALERT_MARKER's own comment
# above for why an org-wide alert needs its own message marker rather than
# maybe_notify_performance_alert()'s generic null-lead_id dedup check).
FOCUS_SHIFT_ALERT_MARKER = "focando nos leads errados"


def build_action_queue(leads: list[LeadResponse]) -> list[LeadResponse]:
    """Execution-engine round — the deterministic "what do I do next, in
    order" queue GET /workday/action-queue (workday.py) and
    get_next_mandatory_lead() below both read. Pure, no DB access: takes
    whatever rank_leads_by_priority()'s own already-scored candidate pool
    the caller passes in — same "reuse, don't re-query" precedent every
    other workday_engine.py aggregation already follows.

    Filtered to leads with an actual recommended action
    (next_best_action_type is not None — always None for a converted lead,
    compute_action_type_and_urgency, scoring.py) and not already closed
    either way (status not in converted/lost — a *lost* lead still gets
    next_best_action_type == "drop_lead", so the status check catches
    what the type-nullness check alone wouldn't).

    Sorted deal_risk_level first (critical > high > medium > low), then
    expected_value/win_probability/response_delay_minutes (each DESC,
    nulls sorted last) — "how bad could it get" before "how much money"
    before "how likely" before "how long ignored." Money-first override
    (Task 6): any lead worth >= _MONEY_FIRST_THRESHOLD is pulled into the
    queue's own top _MONEY_FIRST_TOP_SLOTS positions regardless of risk
    tier — a deal that big jumps the line even past a merely medium-risk
    one, though a *critical*-risk lead worth that much would already be
    there on its own merits without the override. Capped to
    _ACTION_QUEUE_LIMIT."""
    candidates = [
        lead
        for lead in leads
        if lead.next_best_action_type is not None and lead.status not in ("converted", "lost")
    ]
    candidates.sort(
        key=lambda lead: (
            -_RISK_LEVEL_ORDER.get(lead.deal_risk_level, 0),
            -lead.expected_value,
            -lead.win_probability,
            lead.response_delay_minutes is None,
            -(lead.response_delay_minutes or 0),
        )
    )

    forced = [lead for lead in candidates if lead.expected_value >= _MONEY_FIRST_THRESHOLD][
        :_MONEY_FIRST_TOP_SLOTS
    ]
    forced_ids = {lead.id for lead in forced}
    ordered = forced + [lead for lead in candidates if lead.id not in forced_ids]

    return ordered[:_ACTION_QUEUE_LIMIT]


def get_next_mandatory_lead(queue: list[LeadResponse]) -> LeadResponse | None:
    """Execution-engine round's "hard focus mode" — the ONE lead the user
    is pointed at right now, out of build_action_queue()'s own ordered top
    10. Prefers whichever comes first in queue order that's either
    deal_risk_level == "critical" or has gone unanswered for over
    _MANDATORY_PENDING_RESPONSE_MINUTES minutes (response_delay_minutes);
    falls back to the queue's own first entry (already the single
    highest-priority lead by build_action_queue()'s own ordering) when
    neither condition is met by anything in it."""
    for lead in queue:
        if lead.deal_risk_level == "critical" or (
            lead.response_delay_minutes is not None
            and lead.response_delay_minutes > _MANDATORY_PENDING_RESPONSE_MINUTES
        ):
            return lead
    return queue[0] if queue else None


async def get_next_actionable_lead(
    db: AsyncSession, organization_id: str, *, exclude_lead_id: uuid.UUID | None = None
) -> LeadResponse | None:
    """One lead to work on next for POST /workday/complete-and-next — same
    ranking rank_leads_by_priority() gives everywhere else it's used.
    Dynamic Deal Reallocation (Task 2, revenue-maximization round) changed
    what that ranking actually optimizes for: deal_risk_level (critical
    first), then expected_value/win_probability/opportunity_cost/score, all
    DESC — revenue-first, not the "overdue first" urgency-bucket ordering
    this function's own docstring used to describe (GET /leads/priority
    keeps that original ordering in its own separate implementation,
    unaffected).

    exclude_lead_id skips the lead the caller just completed — it usually
    wouldn't resurface anyway (its next_action is now cleared, so its own
    expected_value/win_probability typically drop with it), but a small org
    with few other leads could otherwise hand the same lead right back."""
    ranked = await rank_leads_by_priority(db, organization_id)
    for response in ranked:
        if exclude_lead_id is not None and response.id == exclude_lead_id:
            continue
        return response
    return None


async def complete_lead_task(
    db: AsyncSession, lead: Lead, *, organization_id: str, user_email: str | None
) -> bool:
    """Shared body of POST /leads/{id}/complete-task and POST
    /workday/complete-and-next: logs the completion to LeadActivityLog
    (captured before clearing, so the timeline still shows what was done),
    clears next_action/next_action_due_at, and ends the caller's in-focus
    session on this lead if they hold one — identical behavior to the
    existing endpoint, just factored out so the new workday loop doesn't
    duplicate it. Returns False (nothing to do, caller should 400) when the
    lead has no next_action to complete; True otherwise. Caller commits."""
    if lead.next_action is None:
        return False

    now = datetime.now(timezone.utc)
    duration_seconds = None
    if lead.in_focus and lead.focused_by_email == user_email and lead.focused_at is not None:
        duration_seconds = int((now - lead.focused_at).total_seconds())
        lead.in_focus = False
        lead.focused_at = None
        lead.focused_by_email = None

    db.add(
        LeadActivityLog(
            organization_id=organization_id,
            lead_id=lead.id,
            lead_name=lead.name,
            event_type="task_completed",
            message=f"Task completed: {lead.next_action}",
            user_email=user_email,
            duration_seconds=duration_seconds,
        )
    )
    lead.next_action = None
    lead.next_action_due_at = None
    return True


def format_brl(value: float) -> str:
    """1234567.0 -> '1.234.567' — pt-BR thousands separator, no decimals
    (this is a rough estimate, not exact currency). Shared by
    _build_focus_message (workday.py) and generate_accountability_message
    below, so the two money-mentioning sentences format it identically."""
    return f"{value:,.0f}".replace(",", ".")


def detect_user_failure_state(*, completion_rate: float, overdue_tasks: int) -> FailureState:
    """"on_track" / "at_risk" / "failing" — a plain rule table over GET
    /workday/performance's own completion_rate/overdue_tasks, no ML.
    completion_rate can run above 1.0 (someone can complete more today than
    was strictly due today) — that still reads as on_track, which is
    correct."""
    if completion_rate < _FAILING_COMPLETION_RATE or overdue_tasks > _FAILING_OVERDUE_THRESHOLD:
        return "failing"
    if completion_rate < _AT_RISK_COMPLETION_RATE:
        return "at_risk"
    return "on_track"


def generate_accountability_message(
    *,
    failure_state: FailureState,
    completion_rate: float,
    overdue_tasks: int,
    leads_ignored_yesterday: int,
    estimated_revenue_lost: float,
    tasks_remaining_today: int,
) -> str:
    """The Performance Panel's (and Command Center's) headline sentence for
    the caller's current failure_state — built here, not the frontend, same
    "backend writes the sentence" rule the timeline/activity feed and
    _build_focus_message already follow. Leads with the financial framing
    (leads_ignored_yesterday and estimated_revenue_lost both > 0 — a lead
    only contributes revenue once it's been enriched, see
    get_lead_estimated_value()) whenever there's a real number to show;
    falls back to a plain activity-count message otherwise, in both
    failing and at_risk.

    Within "failing", a stricter "high pressure" tier (overdue >
    _HIGH_PRESSURE_OVERDUE_THRESHOLD or completion_rate below
    _HIGH_PRESSURE_COMPLETION_RATE) gets the harshest copy — this is a
    messaging-only distinction, not a new failure_state value, so the
    frontend's existing 3-way color mapping needs no change."""
    has_revenue_impact = leads_ignored_yesterday > 0 and estimated_revenue_lost > 0
    is_high_pressure = (
        overdue_tasks > _HIGH_PRESSURE_OVERDUE_THRESHOLD
        or completion_rate < _HIGH_PRESSURE_COMPLETION_RATE
    )

    if failure_state == "failing":
        if is_high_pressure and has_revenue_impact:
            return (
                "Você está deixando dinheiro na mesa. "
                f"R$ {format_brl(estimated_revenue_lost)} em risco agora."
            )
        if has_revenue_impact:
            return (
                f"Você ignorou {leads_ignored_yesterday} leads que podem gerar "
                f"R$ {format_brl(estimated_revenue_lost)}. Aja agora antes que vire prejuízo real."
            )
        if is_high_pressure:
            return "Você está deixando dinheiro na mesa. Aja agora."
        return f"Você está atrasado em {overdue_tasks} leads. Aja agora antes que piore."
    if failure_state == "at_risk":
        focus_count = max(tasks_remaining_today, 1)
        if has_revenue_impact:
            return (
                f"Você ainda pode recuperar seu dia. Foque nos próximos {focus_count} leads "
                f"antes de perder R$ {format_brl(estimated_revenue_lost)}."
            )
        return "Seu desempenho está abaixo do ideal. Foque nos próximos leads."
    return "Bom ritmo. Continue assim para fechar mais negócios hoje."


# Sales-operating-system round — maybe_notify_ignored_leads()/
# maybe_notify_pipeline_risk() are both org-wide, null-lead_id alerts like
# maybe_notify_performance_alert() below, but that function's own dedup
# check ("any null-lead_id row in the window") assumes it's the *only*
# kind of org-wide alert — see its own docstring. Adding two more under
# that same generic check would let all three silently share (and starve)
# one 6h budget between unrelated triggers, so each gets its own message
# marker to dedupe on instead — the same "structured info via string
# matching" technique LOSS_REASON_MARKER (scoring.py) already established,
# just a `contains` substring anchor instead of a strict prefix, since the
# varying count/value sits at the very start of each message.
IGNORED_LEADS_ALERT_MARKER = "ignorando suas mensagens"
PIPELINE_RISK_ALERT_MARKER = "do seu pipeline está em risco"


async def maybe_notify_ignored_leads(
    db: AsyncSession, *, organization_id: str, user_email: str, ignored_count: int, now: datetime
) -> bool:
    """Sales-operating-system round — fires when more than
    _IGNORED_LEADS_ALERT_THRESHOLD leads are stuck in has_pending_response
    with over a 24h response_delay_minutes (scoring.py) — "you're being
    ignored, at scale." See IGNORED_LEADS_ALERT_MARKER's own comment above
    for why this dedupes on its own message marker rather than
    maybe_notify_performance_alert()'s generic null-lead_id check. Caller
    commits; returns whether a row was actually staged."""
    if ignored_count <= _IGNORED_LEADS_ALERT_THRESHOLD:
        return False

    cutoff = now - timedelta(hours=_IGNORED_LEADS_ALERT_DEDUP_HOURS)
    recent_stmt = select(UserNotification.id).where(
        UserNotification.organization_id == organization_id,
        UserNotification.user_email == user_email,
        UserNotification.message.contains(IGNORED_LEADS_ALERT_MARKER),
        UserNotification.created_at >= cutoff,
    )
    already_sent = (await db.execute(recent_stmt)).scalar_one_or_none()
    if already_sent is not None:
        return False

    db.add(
        UserNotification(
            organization_id=organization_id,
            user_email=user_email,
            lead_id=None,
            message=f"Você tem {ignored_count} leads {IGNORED_LEADS_ALERT_MARKER} agora.",
        )
    )
    return True


async def maybe_notify_pipeline_risk(
    db: AsyncSession, *, organization_id: str, user_email: str, revenue_at_risk: float, now: datetime
) -> bool:
    """Sales-operating-system round — fires when revenue_at_risk (the same
    probability-weighted figure GET /workday/summary already computes,
    compute_revenue_at_risk() in this module) clears
    _PIPELINE_RISK_ALERT_THRESHOLD. Same own-marker dedup shape as
    maybe_notify_ignored_leads() above, for the same reason. Caller
    commits; returns whether a row was actually staged."""
    if revenue_at_risk <= _PIPELINE_RISK_ALERT_THRESHOLD:
        return False

    cutoff = now - timedelta(hours=_PIPELINE_RISK_ALERT_DEDUP_HOURS)
    recent_stmt = select(UserNotification.id).where(
        UserNotification.organization_id == organization_id,
        UserNotification.user_email == user_email,
        UserNotification.message.contains(PIPELINE_RISK_ALERT_MARKER),
        UserNotification.created_at >= cutoff,
    )
    already_sent = (await db.execute(recent_stmt)).scalar_one_or_none()
    if already_sent is not None:
        return False

    db.add(
        UserNotification(
            organization_id=organization_id,
            user_email=user_email,
            lead_id=None,
            message=f"R$ {format_brl(revenue_at_risk)} {PIPELINE_RISK_ALERT_MARKER} hoje.",
        )
    )
    return True


async def maybe_notify_performance_alert(
    db: AsyncSession, *, organization_id: str, user_email: str, message: str, now: datetime
) -> bool:
    """Persists a "failing"-state alert to UserNotification (so it also
    shows in the notification bell, same channel automation "notify"
    actions already use) — but only if the caller isn't due for a repeat
    yet. Deduped on lead_id IS NULL within _PERFORMANCE_ALERT_DEDUP_HOURS,
    excluding maybe_notify_ignored_leads()/maybe_notify_pipeline_risk()'s
    own rows by their message markers (sales-operating-system round —
    those two are also null-lead_id but dedupe on their own schedule; without
    excluding them here, one of *their* alerts landing first would make this
    check think a performance alert had already gone out, and skip a real
    one). Every other notification kind always carries a lead_id (see
    automation_engine.py's own notify path, which only persists a row when
    the lead has an owner), so this is otherwise unambiguous. Caller
    commits; returns whether a row was actually staged."""
    cutoff = now - timedelta(hours=_PERFORMANCE_ALERT_DEDUP_HOURS)
    recent_alert_stmt = select(UserNotification.id).where(
        UserNotification.organization_id == organization_id,
        UserNotification.user_email == user_email,
        UserNotification.lead_id.is_(None),
        UserNotification.created_at >= cutoff,
        ~UserNotification.message.contains(IGNORED_LEADS_ALERT_MARKER),
        ~UserNotification.message.contains(PIPELINE_RISK_ALERT_MARKER),
    )
    already_sent = (await db.execute(recent_alert_stmt)).scalar_one_or_none()
    if already_sent is not None:
        return False

    db.add(
        UserNotification(
            organization_id=organization_id,
            user_email=user_email,
            lead_id=None,
            message=message,
        )
    )
    return True


async def maybe_notify_high_value_leads(
    db: AsyncSession, *, organization_id: str, leads: list[LeadResponse], now: datetime
) -> int:
    """Per-lead "this one's worth acting on now" alert — fires for a
    non-converted lead worth >= _HIGH_VALUE_ALERT_THRESHOLD that's either
    overdue or idle for over _HIGH_VALUE_ALERT_IDLE_DAYS. Takes an
    already-scored list (typically rank_leads_by_priority()'s own result,
    which the caller usually already computed for something else) rather
    than querying again — zero new candidate query, only the per-lead dedup
    check below.

    Deduped per lead_id within _HIGH_VALUE_ALERT_DEDUP_HOURS — unlike
    maybe_notify_performance_alert()'s org-wide null-lead_id dedup, this one
    is keyed on the specific lead, so two different high-value leads going
    cold on the same day each get their own alert. Skips leads with no
    owner_email — same constraint the existing notify-automation path
    already has (UserNotification.user_email is required NOT NULL; an
    unowned lead has nobody specific to notify persistently). Caller
    commits; returns how many notifications were actually staged."""
    candidates = [
        lead
        for lead in leads
        if lead.status != "converted"
        and lead.owner_email is not None
        and lead.estimated_value >= _HIGH_VALUE_ALERT_THRESHOLD
        and (lead.is_overdue or (now - lead.updated_at).days > _HIGH_VALUE_ALERT_IDLE_DAYS)
    ]
    if not candidates:
        return 0

    cutoff = now - timedelta(hours=_HIGH_VALUE_ALERT_DEDUP_HOURS)
    lead_ids = [lead.id for lead in candidates]
    already_notified_stmt = select(UserNotification.lead_id).where(
        UserNotification.organization_id == organization_id,
        UserNotification.lead_id.in_(lead_ids),
        UserNotification.created_at >= cutoff,
    )
    already_notified_ids = set((await db.execute(already_notified_stmt)).scalars().all())

    notified = 0
    for lead in candidates:
        if lead.id in already_notified_ids:
            continue
        days_idle = (now - lead.updated_at).days
        db.add(
            UserNotification(
                organization_id=organization_id,
                user_email=lead.owner_email,
                lead_id=lead.id,
                message=f"Lead de R$ {format_brl(lead.estimated_value)} parado há {days_idle} dias.",
            )
        )
        notified += 1
    return notified


async def maybe_notify_critical_deals(
    db: AsyncSession, *, organization_id: str, leads: list[LeadResponse], now: datetime
) -> int:
    """AI Deal Coach round — the "you're about to lose this" alert for any
    lead score_leads() has already flagged deal_risk_level == "critical".
    Same shape as maybe_notify_high_value_leads() just above (already-scored
    list, no new candidate query; per-lead dedup within
    _CRITICAL_DEAL_ALERT_DEDUP_HOURS; skips leads with no owner_email to
    notify) — kept as its own function rather than folded into that one
    since the two trigger on genuinely different conditions (deal_risk_level
    vs. a flat value+idle-days check) even though they share a dedup
    mechanism. Caller commits; returns how many notifications were actually
    staged."""
    candidates = [
        lead for lead in leads if lead.deal_risk_level == "critical" and lead.owner_email is not None
    ]
    if not candidates:
        return 0

    cutoff = now - timedelta(hours=_CRITICAL_DEAL_ALERT_DEDUP_HOURS)
    lead_ids = [lead.id for lead in candidates]
    already_notified_stmt = select(UserNotification.lead_id).where(
        UserNotification.organization_id == organization_id,
        UserNotification.lead_id.in_(lead_ids),
        UserNotification.created_at >= cutoff,
    )
    already_notified_ids = set((await db.execute(already_notified_stmt)).scalars().all())

    notified = 0
    for lead in candidates:
        if lead.id in already_notified_ids:
            continue
        db.add(
            UserNotification(
                organization_id=organization_id,
                user_email=lead.owner_email,
                lead_id=lead.id,
                message=f"Você pode perder R$ {format_brl(lead.expected_value)} hoje.",
            )
        )
        notified += 1
    return notified


async def maybe_notify_high_revenue_opportunity(
    db: AsyncSession, *, organization_id: str, leads: list[LeadResponse], now: datetime
) -> int:
    """Revenue-loop round — proactively flags a lead that's both a big deal
    (expected_value >= _HIGH_REVENUE_OPPORTUNITY_THRESHOLD — already
    probability-weighted, so on its own this could still fire on a huge but
    only-somewhat-likely deal) AND a real bet to close (win_probability >=
    _HIGH_REVENUE_OPPORTUNITY_WIN_PROBABILITY): the two together read as
    "close this one, don't just watch it," distinct from
    maybe_notify_high_value_leads() above (which triggers on size plus
    neglect, not size plus likelihood) and maybe_notify_critical_deals()
    (which triggers on risk, the opposite signal — a deal already going
    well). Same already-scored-list, no-new-candidate-query, per-lead
    dedup, no-owner-skip shape as those two, and shares their same plain
    lead_id+created_at dedup check (not scoped to its own message, by the
    same design those two already accept — see IGNORED_LEADS_ALERT_MARKER's
    own comment for why only the *org-wide* alerts needed a distinct
    marker).

    Elite round (Task 6) added a third condition on top of the original
    two: days_since_last_activity > _HIGH_REVENUE_OPPORTUNITY_IDLE_DAYS —
    without it this could fire on a deal the owner is actively working
    right now, which isn't really "you're about to lose this." Caller
    commits; returns how many notifications were actually staged."""
    candidates = [
        lead
        for lead in leads
        if lead.owner_email is not None
        and lead.expected_value >= _HIGH_REVENUE_OPPORTUNITY_THRESHOLD
        and lead.win_probability >= _HIGH_REVENUE_OPPORTUNITY_WIN_PROBABILITY
        and lead.days_since_last_activity > _HIGH_REVENUE_OPPORTUNITY_IDLE_DAYS
    ]
    if not candidates:
        return 0

    cutoff = now - timedelta(hours=_HIGH_REVENUE_OPPORTUNITY_ALERT_DEDUP_HOURS)
    lead_ids = [lead.id for lead in candidates]
    already_notified_stmt = select(UserNotification.lead_id).where(
        UserNotification.organization_id == organization_id,
        UserNotification.lead_id.in_(lead_ids),
        UserNotification.created_at >= cutoff,
    )
    already_notified_ids = set((await db.execute(already_notified_stmt)).scalars().all())

    notified = 0
    for lead in candidates:
        if lead.id in already_notified_ids:
            continue
        db.add(
            UserNotification(
                organization_id=organization_id,
                user_email=lead.owner_email,
                lead_id=lead.id,
                message=(
                    f"Você tem uma oportunidade de R$ {format_brl(lead.expected_value)} "
                    "com alta chance de fechar."
                ),
            )
        )
        notified += 1
    return notified


async def maybe_notify_focus_shift(
    db: AsyncSession, *, organization_id: str, user_email: str, leads: list[LeadResponse], now: datetime
) -> bool:
    """Revenue-maximization round (Task 5) — an org-wide nudge (not
    per-lead, since the point is redirecting overall attention, not
    flagging one specific lead): fires when the user has recently touched
    (days_since_last_activity <= _FOCUS_SHIFT_RECENT_ACTIVITY_DAYS) a lead
    whose opportunity_cost (Task 1's own highest_expected_value minus this
    lead's own expected_value, scoring.py) clears
    _FOCUS_SHIFT_OPPORTUNITY_COST_THRESHOLD — a real higher-value lead
    sitting elsewhere while this one gets the attention. Takes an already-
    scored `leads` list, zero new candidate query. Same org-wide, own-
    marker dedup shape as maybe_notify_ignored_leads()/
    maybe_notify_pipeline_risk() above. Caller commits; returns whether a
    row was actually staged."""
    worst_offender = max(
        (
            lead
            for lead in leads
            if lead.days_since_last_activity <= _FOCUS_SHIFT_RECENT_ACTIVITY_DAYS
        ),
        key=lambda lead: lead.opportunity_cost,
        default=None,
    )
    if worst_offender is None or worst_offender.opportunity_cost <= _FOCUS_SHIFT_OPPORTUNITY_COST_THRESHOLD:
        return False

    cutoff = now - timedelta(hours=_FOCUS_SHIFT_ALERT_DEDUP_HOURS)
    recent_stmt = select(UserNotification.id).where(
        UserNotification.organization_id == organization_id,
        UserNotification.user_email == user_email,
        UserNotification.message.contains(FOCUS_SHIFT_ALERT_MARKER),
        UserNotification.created_at >= cutoff,
    )
    already_sent = (await db.execute(recent_stmt)).scalar_one_or_none()
    if already_sent is not None:
        return False

    db.add(
        UserNotification(
            organization_id=organization_id,
            user_email=user_email,
            lead_id=None,
            message=(
                f"Você está {FOCUS_SHIFT_ALERT_MARKER}. Existe uma oportunidade maior de "
                f"R$ {format_brl(worst_offender.opportunity_cost)}."
            ),
        )
    )
    return True


def compute_lost_opportunity_today(ranked: list[LeadResponse]) -> int:
    """"Oportunidade perdida hoje" (Task 6, revenue-maximization round) —
    sum of opportunity_cost (Task 1, scoring.py) across leads not touched
    today (days_since_last_activity >= 1): leads sitting idle right now,
    weighted by how much revenue upside each one represents versus the
    org's single highest-value lead. Reuses whatever rank_leads_by_priority()
    already scored, zero extra query. Moved here from workday.py's own
    router module (Adaptive Intelligence round) — public now (no longer
    router-private) so the new GET /intelligence/exec-insight endpoint
    (routers/intelligence.py) can reuse this exact sum too, without a
    router importing from another router."""
    return sum(
        response.opportunity_cost
        for response in ranked
        if response.days_since_last_activity >= 1 and response.status not in ("converted", "lost")
    )


def compute_revenue_at_risk(
    ranked: list[LeadResponse], *, now: datetime, stale_cutoff: datetime
) -> int:
    """"Money genuinely at risk, probability-adjusted" — contacted leads
    that are either overdue or stale (updated_at older than stale_cutoff),
    summed by expected_value (not the raw estimated_value
    estimated_revenue_at_risk/estimated_revenue_lost elsewhere use). Reuses
    whatever rank_leads_by_priority() already scored — zero extra query.
    Moved here from workday.py's own router module (product-consolidation
    round) — public now (no longer router-private) so the new GET
    /product/summary endpoint (routers/product.py) can reuse this exact sum
    too, without a router importing from another router."""
    total = 0
    for response in ranked:
        if response.status != "contacted":
            continue
        is_overdue = (
            response.next_action_due_at is not None and response.next_action_due_at < now
        )
        is_stale = response.updated_at < stale_cutoff
        if is_overdue or is_stale:
            total += response.expected_value
    return total


def sum_today_potential_revenue(ranked: list[LeadResponse], *, now: datetime) -> int:
    """The Command Center's "Hoje você pode gerar R$ X" — expected_value
    summed over today's actionable leads (overdue or due today). Reuses the
    same already-scored ranked list compute_revenue_at_risk does. Moved
    here from workday.py's own router module (product-consolidation round)
    for the same cross-router-reuse reason as compute_revenue_at_risk
    above."""
    total = 0
    for response in ranked:
        due = response.next_action_due_at
        if due is None:
            continue
        if response.is_overdue or due.date() == now.date():
            total += response.expected_value
    return total


def derive_required_action_and_reason(mandatory_lead: LeadResponse) -> tuple[str, str]:
    """GET /workday/enforcement-state's own required_action/reason
    derivation (Autonomous-sales-OS round), extracted into its own function
    (product-consolidation round) so every caller that needs "what to do
    about this mandatory lead, in words" reuses the exact same branching
    instead of re-deriving it — this is what guarantees
    compute_global_decision()'s own next_action can never disagree with
    GET /workday/enforcement-state's required_action (Task 5). Mirrors
    get_next_mandatory_lead()'s own OR condition, checked in the same order
    (critical first) so the reason always names whichever condition
    actually applied."""
    if mandatory_lead.deal_risk_level == "critical":
        reason = "Você tem um lead crítico que precisa de ação imediata"
    elif mandatory_lead.response_delay_minutes is not None and mandatory_lead.response_delay_minutes > 60:
        reason = "Um lead está aguardando resposta há mais de 60 minutos"
    else:
        reason = "Ação necessária agora"

    required_action = mandatory_lead.next_best_action_type
    if required_action not in ("send_message", "call_now", "schedule_meeting"):
        required_action = "send_message"

    return required_action, reason


async def compute_daily_target_revenue(db: AsyncSession, organization_id: str, cutoff: datetime) -> float:
    """GET /workday/target's revenue-based target (Autonomous-sales-OS
    round) — average converted revenue per day over the last
    DAILY_TARGET_REVENUE_WINDOW_DAYS: sums estimated_value for every lead
    with a "lead_won" LeadActivityLog entry (the same precise conversion-
    moment marker compute_revenue_summary()'s own revenue_generated_today
    reads, scoring.py) since `cutoff`, divided by the window length. 0.0
    with no conversions in the window — a real "nothing to average yet"
    answer, not a misleading default. Two queries: distinct lead_won
    lead_ids in the window, then those leads' rows for enrichment_data.
    Moved here from workday.py's own router module (product-consolidation
    round) — public now so GET /product/summary (routers/product.py) can
    reuse this exact figure for its own revenue_today_gap, without a router
    importing from another router."""
    won_ids_stmt = (
        select(LeadActivityLog.lead_id)
        .distinct()
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type == "lead_won",
            LeadActivityLog.created_at >= cutoff,
        )
    )
    won_ids = (await db.execute(won_ids_stmt)).scalars().all()
    if not won_ids:
        return 0.0

    won_leads_stmt = select(Lead).where(Lead.id.in_(won_ids))
    won_leads = (await db.execute(won_leads_stmt)).scalars().all()
    total = sum(get_lead_estimated_value(lead) for lead in won_leads)
    return total / DAILY_TARGET_REVENUE_WINDOW_DAYS


# fetch_failure_pattern_rows()'s own window/cap (self-optimizing-revenue-
# brain round) — the one genuinely new query GET /product/summary pays
# for its own failure-correction pass: no existing aggregate joins
# lead_lost against the action_* events that preceded it. Public (moved
# here from routers/product.py, live-console-consistency round) so
# _compute_operations_snapshot() (routers/system.py) can run the exact
# same correction pass /product/summary does, without a router importing
# from another router.
FAILURE_PATTERN_WINDOW_DAYS = 90
FAILURE_PATTERN_ROW_LIMIT = 2000


async def fetch_failure_pattern_rows(db: AsyncSession, organization_id: str, *, cutoff: datetime) -> list[dict]:
    """One bounded query backing compute_failure_patterns()'s own
    activities["rows"] (services/leads/intelligence.py) — lead_lost +
    action_call/action_message/action_meeting LeadActivityLog rows, the
    only two event families that function needs and no existing aggregate
    already joins. Moved here from routers/product.py (live-console-
    consistency round) — same query, same shape, not reimplemented."""
    stmt = (
        select(
            LeadActivityLog.lead_id,
            LeadActivityLog.event_type,
            LeadActivityLog.created_at,
            LeadActivityLog.duration_seconds,
        )
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type.in_(
                ("lead_lost", "action_call", "action_message", "action_meeting")
            ),
            LeadActivityLog.created_at >= cutoff,
        )
        .order_by(LeadActivityLog.created_at.asc())
        .limit(FAILURE_PATTERN_ROW_LIMIT)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "lead_id": row.lead_id,
            "event_type": row.event_type,
            "created_at": row.created_at,
            "duration_seconds": row.duration_seconds,
        }
        for row in rows
    ]
