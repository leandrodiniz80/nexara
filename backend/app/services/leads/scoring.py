from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.schemas.leads.lead import (
    ActionEffectivenessResponse,
    ConversionInsightsResponse,
    LeadResponse,
    ResponseMetricsResponse,
    RevenueAttributionResponse,
    ScoreBreakdownItem,
)
from app.schemas.performance import UserPerformanceResponse
from app.services.leads.enrichment import (
    ACTION_ATTEMPT_CLOSE_DEAL,
    ACTION_AWAIT_RESPONSE,
    ACTION_CLOSE_DEAL,
    ACTION_FIRST_CONTACT,
    ACTION_FOLLOW_UP,
    ACTION_MAXIMUM_URGENCY_FOLLOW_UP,
    ACTION_NURTURE_OR_DISCARD,
    ACTION_RESPOND_OR_CALL_NOW,
    ACTION_URGENT_FOLLOW_UP,
    COMPANY_SIZE_PT,
    COMPANY_SIZE_SCORE_IMPACT,
    HIGH_VALUE_INDUSTRIES,
    HIGH_VALUE_LEAD_THRESHOLD,
    INDUSTRY_PT,
    LARGE_COMPANY_SIZES,
    format_brl,
    generate_smart_message,
    get_lead_estimated_value,
)

# "Recent" for the automation-activity boost — same window LeadResponse's
# other "recent" concepts (e.g. GET /leads/attention's default
# stale_after_days) use in this codebase. Also reused as the manual-activity
# ("Recent manual activity" breakdown line) window — one cutoff, one query,
# shared by both.
_RECENT_AUTOMATION_DAYS = 3
# "Task completed in the last 24h" breakdown line's own window — deliberately
# tighter than the 3-day manual-activity window above, since this one is
# specifically about celebrating a *just-finished* task, not general recent
# touch.
_RECENT_TASK_COMPLETION_HOURS = 24
# compute_win_probability()'s "no activity" penalty threshold — same 7-day
# window compute_lead_score's own "Idle for over a week" line already uses.
_WIN_PROBABILITY_IDLE_DAYS = 7
# score_breakdown's "High conversion probability" line only appears at this
# threshold — matches the frontend's own green-badge cutoff (lead-card.tsx),
# so the same lead reads as "high probability" in both places.
_HIGH_WIN_PROBABILITY_THRESHOLD = 70
# Reinforcement bonus compute_lead_score() adds to `score` when
# win_probability clears the threshold above — same magnitude as this
# codebase's other secondary signals (Recent automation activity,
# High-value sector, Larger company all use +10 too).
_HIGH_WIN_PROBABILITY_SCORE_BONUS = 10
# compute_next_best_action()'s "low probability" cutoff (feedback-loop
# round) — same <40 red-badge threshold the frontend's own
# getWinProbabilityVariant (lead-card.tsx) already uses, so a lead reading
# as "red" there is exactly the one nurture-or-discard picks out here.
_LOW_WIN_PROBABILITY_THRESHOLD = 40
# compute_lead_score()'s "no activity" cutoff for the smart follow-up
# escalation penalty (feedback-loop round) — deliberately > (not >=) the
# existing "Contacted with no recent follow-up" line's own 3-day cutoff
# just below, so day 3 gets the original mild warning and day 4+ stacks
# this harsher one on top, same "layers stack additively" precedent this
# function's own docstring already documents for the overdue/idle lines.
_FOLLOW_UP_ESCALATION_IDLE_DAYS = 3
# compute_deal_risk()'s idle-days cutoffs. Sales-operating-system round
# tightened CRITICAL's own bar from >5 to >3 days (its explicit ask); that
# alone would make HIGH's original >3-day check unreachable for a big deal
# (CRITICAL, checked first, would already have caught anything idle >3) —
# so HIGH's own idle floor moves down to >1 day too, carving out a real
# "idle 2-3 days, still winnable" band between the two rather than leaving
# a dead branch. MEDIUM's own >3 threshold is untouched: by the time its
# check runs, CRITICAL/HIGH have already ruled out every *big* deal idle
# >3 days, so MEDIUM's >3 only ever fires for a small deal (which is right
# — it was never gated on deal size to begin with).
_DEAL_RISK_CRITICAL_IDLE_DAYS = 3
_DEAL_RISK_HIGH_IDLE_DAYS = 1
_DEAL_RISK_MEDIUM_IDLE_DAYS = 3
# compute_deal_risk()'s HIGH-tier win_probability floor — the prompt's own
# number, deliberately distinct from _HIGH_WIN_PROBABILITY_THRESHOLD (70):
# that one gates a score bonus for an already-good sign, this one gates
# "worth the alarm" for a stalling deal that still looks winnable.
_DEAL_RISK_HIGH_WIN_PROBABILITY = 60

# compute_lead_score()'s adaptive-scoring bonuses (feedback-loop round) —
# rewarding a lead that matches the org's own real-world highest-converting
# profile (compute_conversion_insights()). Industry counts for more than
# company size since it's historically the stronger conversion signal in
# this codebase's own high-value groupings (HIGH_VALUE_INDUSTRIES already
# outweighs LARGE_COMPANY_SIZES the same way in compute_lead_score's
# existing enrichment section: +10 vs. the size line's own smaller
# contribution).
_CONVERSION_PROFILE_INDUSTRY_BONUS = 10
_CONVERSION_PROFILE_COMPANY_SIZE_BONUS = 8

# Feedback-loop-of-outcomes round — maps a LeadActivityLog event_type to the
# lead_response_state it represents (LeadResponse/scoring.py's own "derived,
# no migration" field — see that model's own docstring). "message_sent" is
# deliberately absent: it's what response_time_minutes is timed *from*, not
# a response state itself.
RESPONSE_STATE_BY_EVENT_TYPE = {
    "lead_responded": "responded",
    "lead_interested": "interested",
    "lead_rejected": "not_interested",
}
# The reverse of the mapping above — POST /leads/{id}/record-response
# (leads.py) uses this to turn its own request body's `response` back into
# the event_type it logs, so the two directions can't drift out of sync.
RESPONSE_EVENT_TYPE_BY_STATE = {state: event_type for event_type, state in RESPONSE_STATE_BY_EVENT_TYPE.items()}
# compute_response_metrics()'s reporting window — the prompt's own number,
# a stable-enough sample without going stale the way an all-time rate would
# as messaging habits/segments shift.
_RESPONSE_METRICS_WINDOW_DAYS = 30
# compute_lead_score()'s response-outcome bonuses/penalty — a real "the
# market told us" signal, so both outweigh every purely-behavioral line
# above (the biggest of which is -30, matched here so a rejection is never
# a *smaller* deal than "task overdue").
_INTERESTED_SCORE_BONUS = 25
_NOT_INTERESTED_SCORE_PENALTY = -30
# compute_lead_score()'s "matches the org's best-responding segment" bonus
# — same magnitude as the feedback-loop round's own adaptive-scoring
# industry bonus (_CONVERSION_PROFILE_INDUSTRY_BONUS), since this is the
# same kind of learned-not-hardcoded signal, just for response rate instead
# of conversion.
_RESPONSE_SEGMENT_BONUS = 10

# Sales-operating-system round — response-loop-completion pressure. Tiered
# (elif), not stacked: a delay classifies as "over 1h" OR "over 24h", same
# escalating-tier style compute_lead_score's own days_idle recency_impact
# block already uses, not the separate "layers stack additively" pattern
# the overdue/idle-escalation lines use (those are independent signals;
# these are one signal read at two severities).
_PENDING_RESPONSE_DELAY_MINUTES_LOW = 60
_PENDING_RESPONSE_DELAY_MINUTES_HIGH = 24 * 60
_PENDING_RESPONSE_PENALTY_LOW = -15
_PENDING_RESPONSE_PENALTY_HIGH = -25
# "Fast response from lead" — same <30min bar compute_response_metrics()'s
# own reporting doesn't hardcode anywhere else, but is a reasonable "this
# lead is unusually engaged" bar given avg_response_time_minutes in
# practice runs much higher. A response, however slow, has already earned
# its own +25/-30 via lead_response_state below; this is an *additional*
# stack on top for a response that was also fast.
_FAST_RESPONSE_MINUTES = 30
_FAST_RESPONSE_BONUS = 15

# Sales-operating-system round — pipeline-value pressure. Same
# HIGH_VALUE_LEAD_THRESHOLD (5000) and _HIGH_WIN_PROBABILITY_THRESHOLD (70)
# bars already used elsewhere in this file, reused rather than duplicated.
_HIGH_VALUE_OVERDUE_PENALTY = -30
_HIGH_VALUE_HIGH_PROBABILITY_BONUS = 20

# Sales-operating-system round — lead-neglect detection, keyed on
# days_since_last_activity (LeadActivityLog-derived) rather than the
# existing updated_at-derived days_idle several lines above already use —
# see LeadResponse.days_since_last_activity's own docstring for why the
# two can diverge. Tiered (elif), same style as the pending-response block
# above.
_NEGLECT_WARNING_DAYS = 3
_NEGLECT_WARNING_PENALTY = -15
_NEGLECT_ABANDONED_DAYS = 7
_NEGLECT_ABANDONED_PENALTY = -30

# compute_lead_score()'s "matches BOTH learned dimensions" bonus — stacks
# on top of (not instead of) the two separate +10/+8 lines above for
# matching just one dimension each; a lead matching both ends up earning
# 10 + 8 + 15 from these three lines combined.
_FULL_PROFILE_MATCH_BONUS = 15

# compute_next_best_action()'s "Tentar fechar negócio agora" floor — a
# stricter bar than _HIGH_WIN_PROBABILITY_THRESHOLD (70)'s own
# ACTION_CLOSE_DEAL, so 70-79 still reads as "close it" while 80+ reads as
# "close it *now*, this is as good as it gets."
_ATTEMPT_CLOSE_WIN_PROBABILITY = 80

# Execution-engine round — compute_lead_score()'s "learned channel"
# bonus: whichever of call_now/send_message has the higher org-wide
# success rate (compute_action_effectiveness()) earns a small reinforcement
# when it's also this lead's own recommended action_type — same magnitude
# as the codebase's other secondary reinforcement signals (Recent
# automation activity, High-value sector, etc. all use small single-digit-
# to-teens bonuses too).
_ACTION_LEARNING_BONUS = 5

# Revenue-loop round — compute_lead_score()'s "real money" bonus: whichever
# action type compute_revenue_attribution() shows has generated the most
# confirmed revenue org-wide earns this when it's also this lead's own
# recommended action_type. Deliberately its own, larger constant than
# _ACTION_LEARNING_BONUS above (5): that one rewards a channel that closes
# more *often* (a success rate); this one rewards a channel that closes for
# more *money* — a stronger, harder signal (actual attributed R$, not a
# percentage), so it outweighs the softer one rather than matching it.
_REVENUE_LEARNING_BONUS = 10
# Maps compute_action_type_and_urgency()'s own machine-readable action_type
# vocabulary to compute_revenue_attribution()'s revenue_by_action keys —
# the two use different words for the same three channels ("call_now" vs.
# "call", etc.) since one is an API-facing action identifier and the other
# is a plain-noun breakdown key a chart/label can render directly.
ACTION_TYPE_TO_REVENUE_LABEL = {
    "call_now": "call",
    "send_message": "message",
    "schedule_meeting": "meeting",
}


def _matches_top_revenue_action(action_type: str | None, top_revenue_action: str | None) -> bool:
    """Shared by compute_lead_score()'s own revenue-learning-bonus block and
    compute_close_probability_boost() (Elite round, Task 1) — both need the
    exact same "is this lead's recommended action the org's own top-earning
    channel" check, previously only inlined once; factored out so the two
    callers can't silently drift apart."""
    return top_revenue_action is not None and ACTION_TYPE_TO_REVENUE_LABEL.get(action_type) == top_revenue_action


def _matches_top_combination(lead: Lead, action_type: str | None, top_combination: str | None) -> bool:
    """Shared by compute_lead_score()'s own winner-pattern-bonus block and
    compute_close_probability_boost() (Elite round, Task 1) — both need the
    exact same "does this lead's own (action, industry, company_size) match
    the org's single best-proven combination" check
    (compute_revenue_attribution()'s top_combination), previously only
    inlined once inside the winner-pattern block; factored out so the two
    callers can't silently drift apart. Same " | "-delimited key format
    compute_revenue_attribution() itself builds (see that function's own
    comment for why not a literal "|")."""
    if top_combination is None or not lead.enrichment_data:
        return False
    industry = lead.enrichment_data.get("industry")
    company_size = lead.enrichment_data.get("company_size")
    action_label = ACTION_TYPE_TO_REVENUE_LABEL.get(action_type)
    if not (action_label and industry and company_size):
        return False
    return f"{action_label} | {industry} | {company_size}" == top_combination

# Autonomous-sales-OS round — compute_lead_score()'s "intelligent pipeline
# pruning" bar: all three conditions must hold (a lead that's merely low-
# probability but still big, or small but idle only briefly, isn't pruned)
# before a lead is flagged as having no real revenue potential left.
_PRUNE_WIN_PROBABILITY_THRESHOLD = 20
_PRUNE_EXPECTED_VALUE_THRESHOLD = 1000
_PRUNE_IDLE_DAYS_THRESHOLD = 7
# Deliberately the harshest single penalty in this function — pruning is
# meant to sink a dead lead's score well below anything a real, still-
# winnable deal could reach from its other penalties alone.
_PRUNE_SCORE_PENALTY = -50

# compute_forecast_value()'s own decay multipliers (Revenue Forecast
# Engine, Autonomous-sales-OS round) — a forecasting-specific haircut on
# top of score_leads()'s own win_probability-weighted expected_value,
# since a stalling deal's plain expected_value overstates how much of that
# money will actually land within the forecast period. Checked overdue
# first (a harsher signal than merely idle — same "worse condition wins"
# precedent compute_deal_risk's own ordering already sets), idle second,
# fresh (1.0, i.e. unchanged) otherwise.
_FORECAST_OVERDUE_DECAY = 0.6
_FORECAST_IDLE_DECAY = 0.7
_FORECAST_IDLE_DECAY_DAYS = 3

# Revenue-maximization round — Opportunity Cost Engine's own bar (Task 1):
# the prompt's own number. "Being interacted with" has no real "selected
# in the UI" signal reaching scoring at all (no such state is ever sent to
# this backend), so this reuses has_recent_manual_activity — already
# computed per lead for other bonuses above — as the closest available
# proxy; see score_leads()'s own comment where it's applied.
#
# Ultimate-Sales-OS round tightened this from 5000 (>) to 3000 (>=) — the
# prompt's own literal bar — so opportunity cost fires as a signal sooner,
# before a big gap has fully formed.
_OPPORTUNITY_COST_THRESHOLD = 3000
_OPPORTUNITY_COST_PENALTY = -40

# Ultimate-Sales-OS round — "PRESSÃO POR RISCO" (Task 1): deal_risk_level
# itself now earns its own direct score bonus, on top of (not instead of)
# every other risk-adjacent penalty above (overdue, stale, high-value-at-
# risk, ...) and on top of compute_deal_risk()'s own separate effect on
# next_best_action_type/urgency. A critical or high-risk deal is exactly
# the kind of thing this system should be pushing the seller toward, so it
# gets rewarded here even though risk_level itself already drove other
# penalties/urgency elsewhere — those measure neglect, this measures "this
# deal needs pressure right now."
_RISK_PRESSURE_CRITICAL_BONUS = 35
_RISK_PRESSURE_HIGH_BONUS = 20

# Dynamic Deal Reallocation's own risk-tier ordering (Task 2,
# rank_leads_by_priority()) — a local copy of workday_engine.py's own
# _RISK_LEVEL_ORDER: that module already imports FROM this one, so the
# reverse import would be circular — same small-duplicated-constant
# precedent format_brl's own two independent copies already established.
_RISK_LEVEL_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}
# rank_leads_by_priority()'s own "force to the top" bar (Task 2) — same
# technique and numbers as build_action_queue()'s own
# _MONEY_FIRST_THRESHOLD/_MONEY_FIRST_TOP_SLOTS (workday_engine.py), kept
# as separate constants here since the two functions share no code, just
# the same prompt-specified numbers.
_REALLOCATION_FORCE_TOP_VALUE = 10000
_REALLOCATION_FORCE_TOP_WIN_PROBABILITY = 70
_REALLOCATION_FORCE_TOP_SLOTS = 3

# Revenue Acceleration Mode's own trigger (Task 3; ratio formula per the
# Ultimate-Sales-OS round's Task 5) — see compute_acceleration_mode()'s own
# docstring for why this is a cheap approximation, not the same precise
# figure GET /workday/target computes (workday.py).
_ACCELERATION_MODE_RATIO_THRESHOLD = 0.7
_ACCELERATION_MODE_TARGET_WINDOW_DAYS = 7
# compute_lead_score()'s acceleration-mode bonuses — the prompt's own +20
# for both signals; both stack independently (a lead can be high-value AND
# high-probability at once, earning both).
_ACCELERATION_HIGH_VALUE_BONUS = 20
_ACCELERATION_HIGH_PROBABILITY_BONUS = 20

# Winner Pattern Replication's own bonus (Task 4) — the single largest
# per-lead bonus in this file: matching the org's own single best-proven
# (action, industry, company_size) combination is a stronger, more
# specific signal than any of the broader "matches a learned dimension"
# bonuses above.
_WINNER_PATTERN_BONUS = 25

# Elite round — "IA de Fechamento" (Task 1): compute_close_probability_boost()'s
# own deltas, the prompt's own literal numbers. Each condition here overlaps,
# by design, with an existing narrower bonus/penalty elsewhere in this
# function (interested-response, fast-response, winner-pattern,
# revenue-learning, pending-response) — this is a second, closing-probability-
# specific lens on the same underlying signals, not a replacement for them;
# same "layers compound, they don't override" precedent this function's own
# docstring already establishes for every other pair of related bonuses.
_CLOSE_BOOST_INTERESTED_BONUS = 20
_CLOSE_BOOST_FAST_RESPONSE_BONUS = 15
_CLOSE_BOOST_TOP_COMBINATION_BONUS = 10
_CLOSE_BOOST_TOP_REVENUE_ACTION_BONUS = 10
_CLOSE_BOOST_IGNORED_PENALTY = -20

# Elite round — Speed-to-Lead Engine (Task 3): a second, harsher lens on the
# same has_pending_response/response_delay_minutes signal the sales-
# operating-system round's own tiered pending-response penalty already
# reads (_PENDING_RESPONSE_PENALTY_LOW/_HIGH above) — deliberately its own,
# larger penalty past one hour, plus a brand-new reward for a message still
# fresh (under 10 minutes old, no reason to worry yet).
_SPEED_TO_LEAD_SLOW_MINUTES = 60
_SPEED_TO_LEAD_SLOW_PENALTY = -25
_SPEED_TO_LEAD_FAST_MINUTES = 10
_SPEED_TO_LEAD_FAST_BONUS = 15

# Elite round — Deal Momentum Score (Task 4): compute_momentum()'s own
# points table, a 0-100 "how much is this deal actually moving right now"
# gauge distinct from score (which blends revenue/risk/momentum together).
_MOMENTUM_RECENT_ACTIVITY_POINTS = 30
_MOMENTUM_RECENT_RESPONSE_POINTS = 40
_MOMENTUM_TASK_COMPLETED_POINTS = 20
_MOMENTUM_IDLE_DECAY_PER_DAY = 5
_MOMENTUM_MAX = 100

# Elite round — Hunter Mode (Task 7): fires on a much lower bar than
# Revenue Acceleration Mode's own gap check — not "today's actionable
# revenue is behind pace" but "the entire open pipeline is structurally too
# thin," worth less than half a single day's own revenue target.
_HUNTER_MODE_PIPELINE_RATIO_THRESHOLD = 0.5
_HUNTER_MODE_NEW_LEAD_BONUS = 25

# Elite round — Auto Drop Inteligente refinement (Task 9): a second,
# value-agnostic pruning trigger alongside the autonomous-sales-OS round's
# original three-condition one (_PRUNE_WIN_PROBABILITY_THRESHOLD/
# _PRUNE_EXPECTED_VALUE_THRESHOLD/_PRUNE_IDLE_DAYS_THRESHOLD above) — a
# lead this unlikely to close and this neglected gets dropped regardless of
# its own expected_value, catching a big-looking but effectively dead deal
# the value-gated rule alone would keep protecting.
_PRUNE_HARD_WIN_PROBABILITY_THRESHOLD = 15
_PRUNE_HARD_IDLE_DAYS_THRESHOLD = 10

# Adaptive Intelligence round — compute_adaptive_weights()'s own bounds
# (Task 1): the prompt's own literal range. 1.0 (unweighted) is always the
# answer for a signal value with too little data to trust yet — see
# _ADAPTIVE_WEIGHTS_MIN_SAMPLE_SIZE below.
_ADAPTIVE_WEIGHTS_WINDOW_DAYS = 30
_ADAPTIVE_WEIGHT_MIN = 0.8
_ADAPTIVE_WEIGHT_MAX = 1.5
# Below this many outcomes (won+lost) for a given signal value, its own
# conversion rate is too noisy to weight anything by — a single won/lost
# lead swinging a multiplier the full 0.8-1.5 range would be gaming the
# score off one data point.
_ADAPTIVE_WEIGHTS_MIN_SAMPLE_SIZE = 3
# "high_risk" signal's own proxy (Task 1): no stored deal_risk_level
# history exists to check against a past outcome (it's computed fresh at
# read time, current state only — see compute_deal_risk()'s own
# docstring), so this reuses each outcome's own time-to-close
# (duration_seconds on its lead_won/lead_lost LeadActivityLog entry,
# already written by PATCH /leads/{id}/status) as a "this one dragged on
# and looked risky along the way" stand-in — a disclosed approximation,
# same spirit as every other proxy this codebase already accepts.
_ADAPTIVE_HIGH_RISK_DAYS_TO_OUTCOME = 7


def compute_close_probability_boost(
    lead: Lead,
    *,
    lead_response_state: str,
    response_time_minutes: int | None,
    has_pending_response: bool,
    response_delay_minutes: int | None,
    matches_top_combination: bool,
    matches_top_revenue_action: bool,
) -> tuple[int, list[ScoreBreakdownItem]]:
    """"IA de Fechamento" (Elite round, Task 1) — a dedicated closing-
    probability lens, called from inside compute_lead_score() and added on
    top of its own running total. Pure, no DB access, same style as every
    other compute_*() helper compute_lead_score() already calls. See the
    _CLOSE_BOOST_* constants' own comment for why this intentionally
    overlaps with several already-existing, narrower bonuses elsewhere in
    compute_lead_score() rather than replacing them."""
    delta = 0
    breakdown: list[ScoreBreakdownItem] = []

    if lead_response_state == "interested":
        breakdown.append(
            ScoreBreakdownItem(
                reason="IA de Fechamento: já respondeu e demonstrou interesse",
                impact=_CLOSE_BOOST_INTERESTED_BONUS,
            )
        )
        delta += _CLOSE_BOOST_INTERESTED_BONUS

    if response_time_minutes is not None and response_time_minutes < _FAST_RESPONSE_MINUTES:
        # <30min — reuses the same fast-response reading response_time_
        # minutes already gives compute_lead_score()'s own _FAST_RESPONSE_*
        # bonus above (same 30-minute bar, _FAST_RESPONSE_MINUTES), just as
        # its own IA-de-Fechamento line item rather than folded into that
        # one.
        breakdown.append(
            ScoreBreakdownItem(
                reason="IA de Fechamento: respondeu rápido (menos de 30 minutos)",
                impact=_CLOSE_BOOST_FAST_RESPONSE_BONUS,
            )
        )
        delta += _CLOSE_BOOST_FAST_RESPONSE_BONUS

    if matches_top_combination:
        breakdown.append(
            ScoreBreakdownItem(
                reason="IA de Fechamento: combina com o padrão que mais converte",
                impact=_CLOSE_BOOST_TOP_COMBINATION_BONUS,
            )
        )
        delta += _CLOSE_BOOST_TOP_COMBINATION_BONUS

    if matches_top_revenue_action:
        breakdown.append(
            ScoreBreakdownItem(
                reason="IA de Fechamento: ação recomendada é a que mais gera receita",
                impact=_CLOSE_BOOST_TOP_REVENUE_ACTION_BONUS,
            )
        )
        delta += _CLOSE_BOOST_TOP_REVENUE_ACTION_BONUS

    if (
        has_pending_response
        and response_delay_minutes is not None
        and response_delay_minutes > _PENDING_RESPONSE_DELAY_MINUTES_HIGH
    ):
        breakdown.append(
            ScoreBreakdownItem(
                reason="IA de Fechamento: ignorou a última mensagem há mais de 24h",
                impact=_CLOSE_BOOST_IGNORED_PENALTY,
            )
        )
        delta += _CLOSE_BOOST_IGNORED_PENALTY

    return delta, breakdown


def compute_momentum(
    lead: Lead,
    *,
    has_recent_manual_activity: bool,
    lead_response_state: str,
    task_completed_recently: bool,
    days_since_last_activity: int,
) -> int:
    """Deal Momentum Score (Elite round, Task 4) — 0-100 "how hot is this
    deal right now" gauge: purely about recent motion (a real touch, a real
    reply, a task just closed), decayed by how many days it's sat idle
    since — distinct from `score`, which blends this together with
    revenue/risk/enrichment signals this function never looks at. Not
    persisted; computed fresh every score_leads() pass like every other
    derived LeadResponse field. "not_interested" doesn't count as momentum
    even though it's a real reply — a rejection isn't forward motion."""
    momentum = 0
    if has_recent_manual_activity:
        momentum += _MOMENTUM_RECENT_ACTIVITY_POINTS
    if lead_response_state not in ("no_response", "not_interested"):
        momentum += _MOMENTUM_RECENT_RESPONSE_POINTS
    if task_completed_recently:
        momentum += _MOMENTUM_TASK_COMPLETED_POINTS

    decay_days = min(days_since_last_activity, _MOMENTUM_MAX // _MOMENTUM_IDLE_DECAY_PER_DAY)
    momentum -= decay_days * _MOMENTUM_IDLE_DECAY_PER_DAY

    return max(0, min(_MOMENTUM_MAX, momentum))


def compute_close_date_prediction(
    lead: Lead, *, avg_time_to_close_days: int | None, win_probability: int
) -> datetime | None:
    """Individual close-date forecast (Elite round, Task 8) —
    lead.created_at plus the org's own avg_time_to_close_days
    (compute_conversion_insights(), read once per score_leads() batch),
    weighted by how far along this lead's own win_probability suggests it
    already is: a lead more likely to close is assumed nearer the end of
    that typical window, one less likely nearer the start (floored at 1 day
    so this is never the exact same instant as created_at). None whenever
    there's no org history to predict from yet (avg_time_to_close_days is
    None/0) or the lead is already converted/lost — nothing left to
    predict."""
    if lead.status in ("converted", "lost"):
        return None
    if not avg_time_to_close_days:
        return None
    days_out = max(1, round(avg_time_to_close_days * (1 - win_probability / 100)))
    return lead.created_at + timedelta(days=days_out)


def compute_win_probability(
    lead: Lead, *, has_recent_manual_activity: bool, task_completed_recently: bool, now: datetime
) -> int:
    """0-100 estimated likelihood this lead converts — a plain rule table
    over status plus the same recent-activity/overdue/enrichment signals
    compute_lead_score() already gathers for its own batch query, no
    ML/LLM. converted/lost short-circuit to 100/0 outright, matching
    those statuses' own compute_lead_score treatment. is_overdue/days_idle
    are recomputed here rather than threaded through as params — same
    "cheap, pure, independently derived" precedent score_leads() already
    sets by computing its own is_overdue separately from
    compute_lead_score's internal check."""
    if lead.status == "converted":
        return 100
    if lead.status == "lost":
        return 0

    probability = 40 if lead.status == "contacted" else 20  # "new"

    if has_recent_manual_activity:
        probability += 15
    if task_completed_recently:
        probability += 10

    is_overdue = lead.next_action_due_at is not None and lead.next_action_due_at < now
    if is_overdue:
        probability -= 20

    days_idle = (now - lead.updated_at).days
    if days_idle > _WIN_PROBABILITY_IDLE_DAYS:
        probability -= 25

    if lead.enrichment_data:
        probability += 10
        if lead.enrichment_data.get("company_size") in LARGE_COMPANY_SIZES:
            probability += 10

    return max(0, min(100, probability))


def compute_next_best_action(
    lead: Lead,
    *,
    is_overdue: bool,
    now: datetime,
    win_probability: int,
    has_pending_response: bool,
    response_delay_minutes: int | None,
    deal_risk_level: str,
) -> str | None:
    """"What should I do about this lead right now" — a plain rule table on
    status (+ overdue), no ML/LLM involved. Converted (and any other status
    outside new/contacted, e.g. lost) has nothing left to act on. Builds on
    ACTION_FIRST_CONTACT/ACTION_URGENT_FOLLOW_UP/ACTION_FOLLOW_UP/
    ACTION_MAXIMUM_URGENCY_FOLLOW_UP/ACTION_CLOSE_DEAL/ACTION_NURTURE_OR_DISCARD/
    ACTION_AWAIT_RESPONSE/ACTION_ATTEMPT_CLOSE_DEAL/ACTION_RESPOND_OR_CALL_NOW
    (enrichment.py) rather than its own string literals, since
    generate_lead_message_by_action() matches on those same prefixes to
    pick a message tone for suggested_message.

    Execution-engine round's "force priority" rule sits above everything
    else, status included: a critical-risk lead with a message still
    unanswered (deal_risk_level == "critical" and has_pending_response)
    always returns ACTION_RESPOND_OR_CALL_NOW, full stop — the prompt's own
    "ALWAYS," so it isn't folded into the "contacted" branch's own ordered
    tree below (deal_risk_level is computed from status/expected_value/
    idle-days already, so this can theoretically apply to any status, not
    just "contacted," though in practice a pending response implies one).

    Otherwise, for a "contacted" lead, one ordered decision tree,
    highest-priority rule first:
      1. A message is out with no reply yet (has_pending_response) and it's
         been over _PENDING_RESPONSE_DELAY_MINUTES_HIGH minutes — stop
         waiting, escalate (same string
         ACTION_URGENT_FOLLOW_UP + " (lead não respondeu)" — its own
         prefix still matches ACTION_URGENT_FOLLOW_UP's message template,
         since generate_lead_message_by_action() matches by prefix, not
         exact string).
      2. A message is out with no reply yet, but still within that window
         — the system just acted; the right move is to wait, not to pile
         on (ACTION_AWAIT_RESPONSE), regardless of anything else below.
      3. No activity in over _FOLLOW_UP_ESCALATION_IDLE_DAYS days — stop
         being passive (this is also compute_lead_score's own escalation-
         penalty trigger).
      4. Its next_action is overdue — the original urgent-follow-up case.
      5. Very high win_probability — as good as this gets; close it now
         (ACTION_ATTEMPT_CLOSE_DEAL).
      6. High win_probability — the deal is warm, go close it
         (ACTION_CLOSE_DEAL).
      7. Low win_probability — not worth aggressive chasing; nurture or
         let it go cold on its own.
      8. Otherwise — the original plain follow-up.
    """
    if deal_risk_level == "critical" and has_pending_response:
        return ACTION_RESPOND_OR_CALL_NOW

    if lead.status == "new":
        action = ACTION_FIRST_CONTACT
    elif lead.status == "contacted":
        days_idle = (now - lead.updated_at).days
        is_long_pending = (
            has_pending_response
            and response_delay_minutes is not None
            and response_delay_minutes > _PENDING_RESPONSE_DELAY_MINUTES_HIGH
        )
        if is_long_pending:
            action = ACTION_URGENT_FOLLOW_UP + " (lead não respondeu)"
        elif has_pending_response:
            action = ACTION_AWAIT_RESPONSE
        elif days_idle > _FOLLOW_UP_ESCALATION_IDLE_DAYS:
            action = ACTION_MAXIMUM_URGENCY_FOLLOW_UP
        elif is_overdue:
            action = ACTION_URGENT_FOLLOW_UP
        elif win_probability >= _ATTEMPT_CLOSE_WIN_PROBABILITY:
            action = ACTION_ATTEMPT_CLOSE_DEAL
        elif win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
            action = ACTION_CLOSE_DEAL
        elif win_probability < _LOW_WIN_PROBABILITY_THRESHOLD:
            action = ACTION_NURTURE_OR_DISCARD
        else:
            action = ACTION_FOLLOW_UP
    else:
        return None

    # ACTION_AWAIT_RESPONSE/ACTION_RESPOND_OR_CALL_NOW excluded: neither
    # reads as a sentence with "com empresa de X de Y" tacked on the way
    # the other actions' own suffixed forms do.
    if lead.enrichment_data and action not in (ACTION_AWAIT_RESPONSE, ACTION_RESPOND_OR_CALL_NOW):
        industry = INDUSTRY_PT.get(lead.enrichment_data.get("industry", ""))
        size = COMPANY_SIZE_PT.get(lead.enrichment_data.get("company_size", ""))
        if industry and size:
            action += f" com empresa de {industry} de {size}"

    return action


# Smart Follow-up Engine's own cadence tables (Task 2, Adaptive
# Intelligence round) — the prompt's own literal day_offset/action pairs.
# day_offset is measured from lead.created_at (no separate "sequence
# started at" column exists — see generate_follow_up_sequence()'s own
# docstring for why this is the right anchor anyway). Kept as a plain
# function over a module-level constant so a future "day_offset in
# business days" refinement doesn't need every caller to change.
def follow_up_sequence_for_state(lead_response_state: str) -> list[dict]:
    """The day_offset/action table half of generate_follow_up_sequence()
    (Task 2) — factored out so a caller holding only a `LeadResponse`
    (auto_execute_engine(), execution_engine.py — Task 3) can look up the
    same cadence without needing the full `Lead` ORM row
    generate_follow_up_sequence() itself requires for its own status
    short-circuit. Computed on demand every call, nothing stored."""
    if lead_response_state == "interested":
        # Escalate: message -> call -> meeting, same cadence spacing as
        # the no-response track below for consistency.
        return [
            {"day_offset": 0, "action": "send_message"},
            {"day_offset": 1, "action": "call_now"},
            {"day_offset": 3, "action": "schedule_meeting"},
        ]
    return [
        {"day_offset": 0, "action": "send_message"},
        {"day_offset": 1, "action": "send_message"},
        {"day_offset": 3, "action": "call_now"},
        {"day_offset": 5, "action": "send_message"},
    ]


def generate_follow_up_sequence(
    lead: Lead, *, lead_response_state: str = "no_response"
) -> list[dict]:
    """Smart Follow-up Engine (Task 2, Adaptive Intelligence round) —
    the fixed, deterministic cadence a lead should be worked on: no-response
    escalates send_message (day 0) -> send_message (day 1) -> call_now
    (day 3) -> send_message, last attempt (day 5); an interested lead
    escalates send_message -> call_now -> schedule_meeting instead (see
    follow_up_sequence_for_state()'s own table). day_offset is measured
    from lead.created_at — this codebase has no separate "sequence
    started" column (see Lead's own docstring), and created_at is already
    the same anchor compute_close_date_prediction() uses for its own
    day-based math, so a caller just checks
    (now - lead.created_at).days against each step's day_offset. Computes
    fresh every call — store NOTHING, per the prompt's own instruction.
    [] for a converted/lost lead (nothing left to follow up on)."""
    if lead.status in ("converted", "lost"):
        return []
    return follow_up_sequence_for_state(lead_response_state)


def compute_lead_score(
    lead: Lead,
    *,
    has_recent_automation: bool,
    has_recent_manual_activity: bool,
    task_completed_recently: bool,
    insights: ConversionInsightsResponse,
    lead_response_state: str,
    best_response_industry: str | None,
    is_overdue: bool,
    win_probability: int,
    expected_value: int,
    has_pending_response: bool,
    response_delay_minutes: int | None,
    response_time_minutes: int | None,
    days_since_last_activity: int,
    action_type: str | None,
    call_success_rate: float | None,
    message_success_rate: float | None,
    top_revenue_action: str | None,
    is_low_potential: bool,
    opportunity_cost: int,
    is_high_opportunity_cost: bool,
    acceleration_mode: bool,
    top_combination: str | None,
    deal_risk_level: str,
    hunter_mode: bool,
    adaptive_weights: dict[str, float],
    now: datetime,
) -> tuple[int, list[ScoreBreakdownItem]]:
    """Dynamic score, computed at read time from the lead's current state —
    never persisted (Lead.score, the stored column, is only this
    computation's starting baseline). Pure: no DB access, so a batch of
    leads can share one query for each of the things this needs beyond the
    lead row itself — see score_leads() below.

    converted leads short-circuit to 100 outright ("score máximo"), no
    other factor considered. Every other status accumulates deltas on top
    of the stored baseline, clamped to [0, 100].

    The "act today or lose it" reinforcement layer (workday command-mode
    round) is deliberately additive on top of the pre-existing overdue/idle
    checks below, not a replacement for them: an overdue, long-idle lead now
    stacks both its original penalty and this layer's, dropping toward 0
    faster than before. That's intentional — the whole point of this layer
    is to make neglect cost visibly more than before.

    win_probability/is_overdue/expected_value are computed by score_leads()
    *before* calling this (sales-operating-system round) rather than
    internally at the end the way win_probability alone used to be: the new
    pipeline-value-pressure lines below need expected_value, which itself
    needs win_probability, so the old "compute it here and return it as a
    third tuple element" shape became circular once expected_value also
    became an input here. score_leads() now computes all three once, up
    front, and passes them to both this function and compute_deal_risk().

    Adaptive Scoring Weights (Task 1, Adaptive Intelligence round) —
    adaptive_weights (compute_adaptive_weights(), computed once per
    score_leads() batch like every other org-wide signal above) rescales a
    handful of specific, already-existing bonuses below — the ones whose
    own signal (industry, company_size, action_type, fast-response,
    deal_risk_level) is exactly what that function measures — by whatever
    real, learned multiplier applies (0.8-1.5, 1.0 wherever there's no key
    for that value yet). Every other bonus/penalty in this function is
    untouched: this is a targeted reweighting of matching components, not
    a rewrite of the scoring model."""
    if lead.status == "converted":
        impact = 100 - lead.score
        return 100, [ScoreBreakdownItem(reason="Lead converted", impact=impact)]

    breakdown: list[ScoreBreakdownItem] = []
    total = lead.score

    if (now - lead.created_at).total_seconds() < 3600:
        fresh_impact = 15
        breakdown.append(
            ScoreBreakdownItem(reason="New lead — fresh opportunity", impact=fresh_impact)
        )
        total += fresh_impact

    days_idle = (now - lead.updated_at).days
    if days_idle >= 14:
        recency_impact = -30
    elif days_idle >= 7:
        recency_impact = -20
    elif days_idle >= 3:
        recency_impact = -10
    else:
        recency_impact = 0
    if recency_impact:
        breakdown.append(
            ScoreBreakdownItem(reason=f"No activity in {days_idle} days", impact=recency_impact)
        )
    total += recency_impact

    if days_idle > 7:
        stale_impact = -25
        breakdown.append(
            ScoreBreakdownItem(reason="Idle for over a week — re-engage today", impact=stale_impact)
        )
        total += stale_impact

    if lead.status == "contacted" and days_idle >= 3:
        contacted_impact = -15
        breakdown.append(
            ScoreBreakdownItem(
                reason="Contacted with no recent follow-up", impact=contacted_impact
            )
        )
        total += contacted_impact

    # Smart follow-up escalation (feedback-loop round) — stacks on top of
    # the -15 line just above rather than replacing it, same "layers
    # compound, they don't override" precedent as the overdue lines below.
    if lead.status == "contacted" and days_idle > _FOLLOW_UP_ESCALATION_IDLE_DAYS:
        escalation_impact = -30
        breakdown.append(
            ScoreBreakdownItem(
                reason="Follow-up overdue — escalating to maximum urgency",
                impact=escalation_impact,
            )
        )
        total += escalation_impact

    if lead.next_action_due_at is not None and lead.next_action_due_at < now:
        overdue_impact = -30
        label = f"Overdue task: {lead.next_action}" if lead.next_action else "Overdue task"
        breakdown.append(ScoreBreakdownItem(reason=label, impact=overdue_impact))
        total += overdue_impact

        action_impact = -20
        breakdown.append(
            ScoreBreakdownItem(reason="Task overdue — act today", impact=action_impact)
        )
        total += action_impact

    # Response-loop-completion pressure (sales-operating-system round) —
    # tiered, not stacked: see _PENDING_RESPONSE_* constants' own comment.
    if has_pending_response and response_delay_minutes is not None:
        if response_delay_minutes > _PENDING_RESPONSE_DELAY_MINUTES_HIGH:
            pending_impact = _PENDING_RESPONSE_PENALTY_HIGH
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Lead ignoring message for over 24h", impact=pending_impact
                )
            )
            total += pending_impact
        elif response_delay_minutes > _PENDING_RESPONSE_DELAY_MINUTES_LOW:
            pending_impact = _PENDING_RESPONSE_PENALTY_LOW
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Lead hasn't responded in over 1h", impact=pending_impact
                )
            )
            total += pending_impact

        # Speed-to-Lead Engine (Elite round, Task 3) — a second, harsher
        # reading of the same pending-delay signal just above (own,
        # distinct constants; see their own comment for why this stacks
        # rather than replaces the tiered penalty above), plus a reward for
        # a message still fresh enough that nobody should be worried yet.
        if response_delay_minutes > _SPEED_TO_LEAD_SLOW_MINUTES:
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Speed-to-Lead: demorando para responder",
                    impact=_SPEED_TO_LEAD_SLOW_PENALTY,
                )
            )
            total += _SPEED_TO_LEAD_SLOW_PENALTY
        elif response_delay_minutes < _SPEED_TO_LEAD_FAST_MINUTES:
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Speed-to-Lead: mensagem recém-enviada",
                    impact=_SPEED_TO_LEAD_FAST_BONUS,
                )
            )
            total += _SPEED_TO_LEAD_FAST_BONUS

    # A response, however slow, already earned its own +25/-30 below via
    # lead_response_state — this is an additional stack on top when it was
    # also fast.
    if (
        lead_response_state != "no_response"
        and response_time_minutes is not None
        and response_time_minutes < _FAST_RESPONSE_MINUTES
    ):
        # Adaptive Scoring Weights (Task 1) — rescaled by "fast_response"
        # when compute_adaptive_weights() has real signal for it.
        fast_response_impact = round(_FAST_RESPONSE_BONUS * adaptive_weights.get("fast_response", 1.0))
        breakdown.append(
            ScoreBreakdownItem(reason="Fast response from lead", impact=fast_response_impact)
        )
        total += fast_response_impact

    # Pipeline-value pressure (sales-operating-system round) — a big deal
    # going overdue costs more than a small one; a big deal that's also
    # likely to close is worth flagging as a reason to prioritize it, not
    # just letting the plain win-probability bonus below speak for it.
    if expected_value >= HIGH_VALUE_LEAD_THRESHOLD and is_overdue:
        breakdown.append(
            ScoreBreakdownItem(
                reason="High-value deal at risk", impact=_HIGH_VALUE_OVERDUE_PENALTY
            )
        )
        total += _HIGH_VALUE_OVERDUE_PENALTY

    if expected_value >= HIGH_VALUE_LEAD_THRESHOLD and win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
        breakdown.append(
            ScoreBreakdownItem(
                reason="High-value high-probability deal",
                impact=_HIGH_VALUE_HIGH_PROBABILITY_BONUS,
            )
        )
        total += _HIGH_VALUE_HIGH_PROBABILITY_BONUS

    # Lead-neglect detection (sales-operating-system round) — tiered, keyed
    # on days_since_last_activity (LeadActivityLog-derived), not the
    # updated_at-derived days_idle the recency_impact/stale_impact lines
    # above already use — see LeadResponse.days_since_last_activity's own
    # docstring for why the two aren't the same measure and both are worth
    # keeping.
    if days_since_last_activity > _NEGLECT_ABANDONED_DAYS:
        breakdown.append(
            ScoreBreakdownItem(reason="Lead abandonado", impact=_NEGLECT_ABANDONED_PENALTY)
        )
        total += _NEGLECT_ABANDONED_PENALTY
    elif days_since_last_activity > _NEGLECT_WARNING_DAYS:
        breakdown.append(
            ScoreBreakdownItem(reason="Lead sem atividade recente", impact=_NEGLECT_WARNING_PENALTY)
        )
        total += _NEGLECT_WARNING_PENALTY

    if has_recent_automation:
        automation_impact = 10
        breakdown.append(
            ScoreBreakdownItem(reason="Recent automation activity", impact=automation_impact)
        )
        total += automation_impact

    if has_recent_manual_activity:
        manual_activity_impact = 10
        breakdown.append(
            ScoreBreakdownItem(reason="Recent manual activity", impact=manual_activity_impact)
        )
        total += manual_activity_impact

    if task_completed_recently:
        completion_impact = 15
        breakdown.append(
            ScoreBreakdownItem(reason="Task completed in the last 24h", impact=completion_impact)
        )
        total += completion_impact

    if lead.enrichment_data:
        industry = lead.enrichment_data.get("industry")
        if industry in HIGH_VALUE_INDUSTRIES:
            # Adaptive Scoring Weights (Task 1) — rescaled by
            # "industry:{industry}" when compute_adaptive_weights() has
            # real signal for this specific industry.
            industry_impact = round(10 * adaptive_weights.get(f"industry:{industry}", 1.0))
            breakdown.append(
                ScoreBreakdownItem(reason=f"High-value sector: {industry}", impact=industry_impact)
            )
            total += industry_impact

        company_size = lead.enrichment_data.get("company_size")
        if company_size in LARGE_COMPANY_SIZES:
            # Adaptive Scoring Weights (Task 1) — rescaled by
            # "company_size:{company_size}" when there's real signal for it.
            size_impact = round(10 * adaptive_weights.get(f"company_size:{company_size}", 1.0))
            breakdown.append(
                ScoreBreakdownItem(
                    reason=f"Larger company: {company_size} employees", impact=size_impact
                )
            )
            total += size_impact

        revenue_impact = COMPANY_SIZE_SCORE_IMPACT.get(company_size, 0)
        if revenue_impact:
            breakdown.append(
                ScoreBreakdownItem(reason="High revenue potential", impact=revenue_impact)
            )
            total += revenue_impact

        # Adaptive scoring (feedback-loop round) — reward matching the
        # org's own real, learned highest-converting profile
        # (compute_conversion_insights()), on top of (not instead of) the
        # static high-value-industry/larger-company lines above, which
        # reward a fixed, hardcoded notion of "good" rather than a learned
        # one.
        if insights.best_industry and industry == insights.best_industry:
            profile_industry_impact = _CONVERSION_PROFILE_INDUSTRY_BONUS
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Matches high-conversion profile: top-converting industry",
                    impact=profile_industry_impact,
                )
            )
            total += profile_industry_impact

        if insights.best_company_size and company_size == insights.best_company_size:
            profile_size_impact = _CONVERSION_PROFILE_COMPANY_SIZE_BONUS
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Matches high-conversion profile: top-converting company size",
                    impact=profile_size_impact,
                )
            )
            total += profile_size_impact

        # Sales-operating-system round — a lead matching BOTH learned
        # dimensions at once earns an additional bonus on top of the two
        # separate ones above, not instead of them.
        if (
            insights.best_industry
            and industry == insights.best_industry
            and insights.best_company_size
            and company_size == insights.best_company_size
        ):
            full_match_impact = _FULL_PROFILE_MATCH_BONUS
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Matches high-conversion profile", impact=full_match_impact
                )
            )
            total += full_match_impact

        # Feedback-loop-of-outcomes round — same "learned, not hardcoded"
        # reward as the two lines above, but for response rate
        # (compute_response_metrics()) rather than conversion.
        if best_response_industry and industry == best_response_industry:
            segment_impact = _RESPONSE_SEGMENT_BONUS
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Matches high-response segment", impact=segment_impact
                )
            )
            total += segment_impact
    else:
        unenriched_impact = -5
        breakdown.append(
            ScoreBreakdownItem(reason="Lead not yet enriched", impact=unenriched_impact)
        )
        total += unenriched_impact

    # Feedback-loop-of-outcomes round — a real "the market told us" signal,
    # not a proxy: outweighs every purely-behavioral line above, same
    # rationale as _INTERESTED_SCORE_BONUS/_NOT_INTERESTED_SCORE_PENALTY's
    # own docstring note.
    if lead_response_state == "interested":
        breakdown.append(
            ScoreBreakdownItem(
                reason="Lead responded and showed interest", impact=_INTERESTED_SCORE_BONUS
            )
        )
        total += _INTERESTED_SCORE_BONUS
    elif lead_response_state == "not_interested":
        breakdown.append(
            ScoreBreakdownItem(
                reason="Lead responded — not interested", impact=_NOT_INTERESTED_SCORE_PENALTY
            )
        )
        total += _NOT_INTERESTED_SCORE_PENALTY

    if win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
        breakdown.append(
            ScoreBreakdownItem(
                reason="High conversion probability", impact=_HIGH_WIN_PROBABILITY_SCORE_BONUS
            )
        )
        total += _HIGH_WIN_PROBABILITY_SCORE_BONUS

    # Execution-engine round — reinforces whichever channel
    # compute_action_effectiveness() (below) has learned actually works
    # better org-wide, but only on top of this lead's own already-
    # recommended action_type (compute_action_type_and_urgency, computed
    # earlier in score_leads() than this call): a lead recommended
    # call_now doesn't get the message bonus just because messages happen
    # to convert better elsewhere, and vice versa. Requires both rates to
    # be real (not None) — no comparison, no bonus, until there's enough
    # actual outcome data to learn from.
    if call_success_rate is not None and message_success_rate is not None:
        # Adaptive Scoring Weights (Task 1) — rescaled by "action:{action_type}"
        # below, same key compute_adaptive_weights() itself derives from
        # this same ActionEffectivenessResponse.
        if action_type == "send_message" and message_success_rate > call_success_rate:
            action_learning_impact = round(
                _ACTION_LEARNING_BONUS * adaptive_weights.get(f"action:{action_type}", 1.0)
            )
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Mensagens historicamente mais eficazes que ligações",
                    impact=action_learning_impact,
                )
            )
            total += action_learning_impact
        elif action_type == "call_now" and call_success_rate > message_success_rate:
            action_learning_impact = round(
                _ACTION_LEARNING_BONUS * adaptive_weights.get(f"action:{action_type}", 1.0)
            )
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Ligações historicamente mais eficazes que mensagens",
                    impact=action_learning_impact,
                )
            )
            total += action_learning_impact

    # Revenue-loop round — reinforces whichever channel compute_revenue_
    # attribution() shows has actually generated the most real, confirmed
    # money org-wide, additive on top of (not a replacement for) the
    # success-rate-based _ACTION_LEARNING_BONUS above: a channel can close
    # more often while still generating less money overall (a smaller
    # average deal size), or vice versa — both are worth rewarding
    # separately. Same "only on top of this lead's own already-recommended
    # action_type" scoping as that bonus, and silent until
    # top_revenue_action is real (not None, i.e. at least one lead has
    # actually converted with attributed revenue behind it).
    matches_top_revenue_action = _matches_top_revenue_action(action_type, top_revenue_action)
    if matches_top_revenue_action:
        breakdown.append(
            ScoreBreakdownItem(
                reason=f"Ação com maior histórico de receita real: {top_revenue_action}",
                impact=_REVENUE_LEARNING_BONUS,
            )
        )
        total += _REVENUE_LEARNING_BONUS

    # Revenue-maximization round — Opportunity Cost Engine (Task 1): a
    # bigger single penalty than any of the learned-channel bonuses above,
    # on purpose — actively working a lead while a much bigger one
    # (> _OPPORTUNITY_COST_THRESHOLD more expected_value) sits neglected is
    # a harder, more concrete signal than any "matches a learned pattern"
    # bonus. is_high_opportunity_cost is computed once by score_leads()
    # (has_recent_manual_activity is its own "being interacted with" proxy
    # — see that function's own comment for why there's no real "selected
    # in the UI" signal to check instead).
    if is_high_opportunity_cost:
        breakdown.append(
            ScoreBreakdownItem(
                reason="Você está deixando de focar em leads que podem gerar mais R$",
                impact=_OPPORTUNITY_COST_PENALTY,
            )
        )
        total += _OPPORTUNITY_COST_PENALTY

    # Ultimate-Sales-OS round — "PRESSÃO POR RISCO" (Task 1): deal_risk_level
    # is computed once by score_leads() (compute_deal_risk(), earlier in its
    # per-lead loop) and passed straight through here.
    # Adaptive Scoring Weights (Task 1) — both tiers rescaled by the same
    # "high_risk" key (compute_adaptive_weights() doesn't distinguish
    # critical from high — both are "a risky deal that still closed" for
    # that signal's own purposes).
    if deal_risk_level == "critical":
        risk_pressure_impact = round(_RISK_PRESSURE_CRITICAL_BONUS * adaptive_weights.get("high_risk", 1.0))
        breakdown.append(
            ScoreBreakdownItem(reason="Risco crítico de perda do negócio", impact=risk_pressure_impact)
        )
        total += risk_pressure_impact
    elif deal_risk_level == "high":
        risk_pressure_impact = round(_RISK_PRESSURE_HIGH_BONUS * adaptive_weights.get("high_risk", 1.0))
        breakdown.append(
            ScoreBreakdownItem(reason="Risco elevado de perda do negócio", impact=risk_pressure_impact)
        )
        total += risk_pressure_impact

    # Revenue Acceleration Mode (Task 3) — when the org is meaningfully
    # behind its daily revenue target (compute_acceleration_mode()), every
    # high-value or high-probability lead gets an extra push, additive on
    # top of (not instead of) this function's own existing high-value/
    # high-probability bonuses above: the system leaning harder into
    # whatever already looks winnable, rather than spreading effort evenly,
    # while the org is playing catch-up.
    if acceleration_mode:
        if expected_value >= HIGH_VALUE_LEAD_THRESHOLD:
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Modo aceleração: lead de alto valor",
                    impact=_ACCELERATION_HIGH_VALUE_BONUS,
                )
            )
            total += _ACCELERATION_HIGH_VALUE_BONUS
        if win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Modo aceleração: alta probabilidade de fechamento",
                    impact=_ACCELERATION_HIGH_PROBABILITY_BONUS,
                )
            )
            total += _ACCELERATION_HIGH_PROBABILITY_BONUS

    # Winner Pattern Replication (Task 4) — compute_revenue_attribution()'s
    # own top_combination (whichever action+industry+company_size has
    # generated the most real revenue org-wide).
    matches_top_combination = _matches_top_combination(lead, action_type, top_combination)
    if matches_top_combination:
        breakdown.append(
            ScoreBreakdownItem(reason="Segue padrão que mais gera receita", impact=_WINNER_PATTERN_BONUS)
        )
        total += _WINNER_PATTERN_BONUS

    # "IA de Fechamento" (Elite round, Task 1) — a dedicated closing-
    # probability lens, on top of (not instead of) every bonus above it
    # overlaps with; see compute_close_probability_boost()'s own docstring.
    close_boost_delta, close_boost_breakdown = compute_close_probability_boost(
        lead,
        lead_response_state=lead_response_state,
        response_time_minutes=response_time_minutes,
        has_pending_response=has_pending_response,
        response_delay_minutes=response_delay_minutes,
        matches_top_combination=matches_top_combination,
        matches_top_revenue_action=matches_top_revenue_action,
    )
    breakdown.extend(close_boost_breakdown)
    total += close_boost_delta

    # Hunter Mode (Elite round, Task 7) — when the org's whole open
    # pipeline is running structurally thin (compute_hunter_mode()), fresh
    # ("new") leads get an extra push so they surface above older,
    # already-being-worked ones: exactly the leads worth chasing when the
    # pipeline itself needs refilling, not just today's queue.
    if hunter_mode and lead.status == "new":
        breakdown.append(
            ScoreBreakdownItem(reason="Modo caçador: lead novo priorizado", impact=_HUNTER_MODE_NEW_LEAD_BONUS)
        )
        total += _HUNTER_MODE_NEW_LEAD_BONUS

    # Autonomous-sales-OS round — intelligent pipeline pruning: a lead
    # this unlikely to close (win_probability), this small even if it did
    # (expected_value), and this neglected (days_since_last_activity) has
    # no real revenue potential left. The harshest single penalty in this
    # function, deliberately — see _PRUNE_SCORE_PENALTY's own comment.
    # is_low_potential is computed once by score_leads() (it also drives
    # that function's own deal_risk_level/next_best_action_type override
    # and build_priority_reason()'s extra clause), not re-derived here.
    if is_low_potential:
        breakdown.append(
            ScoreBreakdownItem(
                reason="Lead sem potencial de receita — recomendado descarte",
                impact=_PRUNE_SCORE_PENALTY,
            )
        )
        total += _PRUNE_SCORE_PENALTY

    return max(0, min(100, total)), breakdown


# Prefix compute_conversion_insights() writes into LeadActivityLog.message
# for a lost-lead outcome entry (see PATCH /leads/{id}/status, leads.py) and
# reads back to aggregate top_loss_reason. There's no metadata/JSONB column
# on LeadActivityLog to carry the reason as structured data (see that
# model's own docstring), so it's encoded in the message behind this fixed
# marker instead — the same "structured info via string matching" technique
# generate_lead_message_by_action() already uses for next_best_action.
LOSS_REASON_MARKER = "Motivo: "

# Performance Feedback Loop (Task 9, Adaptive Intelligence round) — same
# "structured info via string matching" technique as LOSS_REASON_MARKER
# just above, this time for which action channel led to a lead_won/
# lead_lost outcome. Not actually needed by this round's own
# compute_adaptive_weights() (which infers action-effectiveness straight
# from action_call/action_message/action_meeting timestamps, the same
# technique compute_action_effectiveness() already uses — no marker
# required), but written anyway so a human reading the timeline, or a
# future single-row consumer, doesn't have to reconstruct it by joining
# against separate action_* entries.
ACTION_ATTRIBUTION_MARKER = "Ação: "
_ACTION_EVENT_LABEL_PT = {
    "action_call": "ligação",
    "action_message": "mensagem",
    "action_meeting": "reunião",
}
# Reverse of ACTION_EFFECTIVENESS_EVENT_TYPE_BY_ACTION (execution_engine.py)
# — that module already imports FROM this one, so the reverse import would
# be circular (same precedent _RISK_LEVEL_ORDER's own comment already
# explains for a different pair of constants). Used by
# get_last_action_event_type()'s own callers that need the action_type
# vocabulary ("call_now"/"send_message"/"schedule_meeting") rather than
# this module's own PT display label.
ACTION_EVENT_TYPE_TO_ACTION_TYPE = {
    "action_call": "call_now",
    "action_message": "send_message",
    "action_meeting": "schedule_meeting",
}


async def get_last_action_event_type(db: AsyncSession, lead_id) -> str | None:
    """Shared query half of get_last_action_label() below — the raw
    action_call/action_message/action_meeting event_type itself, for a
    caller that needs ACTION_EVENT_TYPE_TO_ACTION_TYPE's own action_type
    vocabulary (update_adaptive_weights_realtime()'s own "action:
    {action_type}" key format, this module) rather than a PT display
    label. None when this lead never had any action_* entry logged."""
    stmt = (
        select(LeadActivityLog.event_type)
        .where(
            LeadActivityLog.lead_id == lead_id,
            LeadActivityLog.event_type.in_(list(_ACTION_EVENT_LABEL_PT)),
        )
        .order_by(LeadActivityLog.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_last_action_label(db: AsyncSession, lead_id) -> str | None:
    """Performance Feedback Loop (Task 9) — the most recent action_call/
    action_message/action_meeting LeadActivityLog entry for this lead, in
    plain Portuguese, for PATCH /leads/{id}/status to attribute a
    conversion/loss to whichever channel was used last. Same "no FK, infer
    by timestamp" approximation compute_action_effectiveness() already
    discloses. None when this lead never had any action_* entry logged."""
    event_type = await get_last_action_event_type(db, lead_id)
    return _ACTION_EVENT_LABEL_PT.get(event_type) if event_type else None


async def compute_conversion_insights(
    db: AsyncSession, organization_id: str
) -> ConversionInsightsResponse:
    """Mines the org's own real outcomes for what actually converts — no
    ML, three plain aggregations over already-recorded data. Every field is
    None until there's enough real signal to say something, rather than a
    misleading default. Exactly two queries regardless of org size (a
    converted-leads row scan, an outcome-log row scan), same "one shared
    query per batch" precedent as score_leads()'s own two queries below —
    called once per score_leads() batch, not per lead.

    best_industry/best_company_size: the most frequent enrichment_data
    value among this org's *converted* leads — "what wins" isn't about
    every lead, only the ones that actually closed.

    avg_time_to_close_days/top_loss_reason: read from LeadActivityLog's
    "lead_won"/"lead_lost" outcome entries (PATCH /leads/{id}/status writes
    these — see leads.py), not LeadStatusHistory: the exact elapsed time is
    already captured per-event on duration_seconds at the moment of the
    transition, which is both simpler and more precise than re-deriving it
    from created_at/a status-history timestamp after the fact.
    """
    converted_stmt = select(Lead.enrichment_data).where(
        Lead.organization_id == organization_id,
        Lead.status == "converted",
        Lead.deleted_at.is_(None),
        Lead.enrichment_data.is_not(None),
    )
    converted_rows = (await db.execute(converted_stmt)).scalars().all()

    industry_counts: dict[str, int] = {}
    company_size_counts: dict[str, int] = {}
    for enrichment_data in converted_rows:
        industry = enrichment_data.get("industry")
        if industry:
            industry_counts[industry] = industry_counts.get(industry, 0) + 1
        company_size = enrichment_data.get("company_size")
        if company_size:
            company_size_counts[company_size] = company_size_counts.get(company_size, 0) + 1

    best_industry = max(industry_counts, key=industry_counts.get) if industry_counts else None
    best_company_size = (
        max(company_size_counts, key=company_size_counts.get) if company_size_counts else None
    )

    outcomes_stmt = select(
        LeadActivityLog.event_type, LeadActivityLog.message, LeadActivityLog.duration_seconds
    ).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type.in_(["lead_won", "lead_lost"]),
    )
    outcome_rows = (await db.execute(outcomes_stmt)).all()

    close_days = [
        row.duration_seconds / 86400
        for row in outcome_rows
        if row.event_type == "lead_won" and row.duration_seconds is not None
    ]
    avg_time_to_close_days = round(sum(close_days) / len(close_days)) if close_days else None

    loss_reason_counts: dict[str, int] = {}
    for row in outcome_rows:
        if row.event_type != "lead_lost" or LOSS_REASON_MARKER not in row.message:
            continue
        reason = row.message.split(LOSS_REASON_MARKER, 1)[1].strip()
        if reason:
            loss_reason_counts[reason] = loss_reason_counts.get(reason, 0) + 1
    top_loss_reason = (
        max(loss_reason_counts, key=loss_reason_counts.get) if loss_reason_counts else None
    )

    return ConversionInsightsResponse(
        best_industry=best_industry,
        best_company_size=best_company_size,
        avg_time_to_close_days=avg_time_to_close_days,
        top_loss_reason=top_loss_reason,
    )


async def compute_response_metrics(
    db: AsyncSession, organization_id: str
) -> ResponseMetricsResponse:
    """Feedback-loop-of-outcomes round — org-wide messaging effectiveness
    mined from the last _RESPONSE_METRICS_WINDOW_DAYS of real outcomes, no
    ML. One query (message_sent/lead_responded/lead_interested/lead_rejected
    LeadActivityLog rows joined to their Lead for industry), aggregated in
    Python — same "one shared query per batch" precedent as
    compute_conversion_insights(). Every rate is 0.0 (not a misleading
    default like a stray None) when there's simply been nothing sent yet;
    avg_response_time_minutes/best_response_industry stay None in that
    case, same "None until there's real signal" rule
    ConversionInsightsResponse's own fields already follow.

    response_rate/interest_rate share the same denominator (messages sent),
    not compounding: interest_rate isn't "of those who responded, how many
    were interested" — it's "of everything sent, how many became
    interested," so the two read as directly comparable percentages of the
    same whole. Both can technically read above 100%: a single sent message
    can accumulate more than one response-type entry over time (e.g.
    "responded" today, "interested" logged later once that conversation
    develops), each counted here — a known approximation, same spirit as
    money_saved_today's own disclosed proxy (workday.py), not a strict
    one-to-one send/response ledger.

    best_response_industry is the industry with the highest per-industry
    response_rate among industries with at least one message sent — "what
    wins" here isn't about every message, only which segment is actually
    replying. Feeds compute_lead_score()'s "Matches high-response segment"
    bonus."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RESPONSE_METRICS_WINDOW_DAYS)
    rows_stmt = (
        select(LeadActivityLog.event_type, LeadActivityLog.duration_seconds, Lead.enrichment_data)
        .join(Lead, Lead.id == LeadActivityLog.lead_id)
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type.in_(list(RESPONSE_STATE_BY_EVENT_TYPE) + ["message_sent"]),
            LeadActivityLog.created_at >= cutoff,
        )
    )
    rows = (await db.execute(rows_stmt)).all()

    sent_count = 0
    responded_count = 0
    interested_count = 0
    response_times_minutes: list[float] = []
    sent_by_industry: dict[str, int] = {}
    responded_by_industry: dict[str, int] = {}

    for row in rows:
        industry = row.enrichment_data.get("industry") if row.enrichment_data else None
        if row.event_type == "message_sent":
            sent_count += 1
            if industry:
                sent_by_industry[industry] = sent_by_industry.get(industry, 0) + 1
            continue

        responded_count += 1
        if industry:
            responded_by_industry[industry] = responded_by_industry.get(industry, 0) + 1
        if row.event_type == "lead_interested":
            interested_count += 1
        if row.duration_seconds is not None:
            response_times_minutes.append(row.duration_seconds / 60)

    response_rate = round(responded_count / sent_count * 100, 1) if sent_count else 0.0
    interest_rate = round(interested_count / sent_count * 100, 1) if sent_count else 0.0
    avg_response_time_minutes = (
        round(sum(response_times_minutes) / len(response_times_minutes), 1)
        if response_times_minutes
        else None
    )

    best_response_industry = (
        max(
            sent_by_industry,
            key=lambda industry: responded_by_industry.get(industry, 0) / sent_by_industry[industry],
        )
        if sent_by_industry
        else None
    )

    return ResponseMetricsResponse(
        response_rate=response_rate,
        interest_rate=interest_rate,
        avg_response_time_minutes=avg_response_time_minutes,
        best_response_industry=best_response_industry,
    )


# Execution-engine round — the "action_*" event types execute_lead_action()
# (execution_engine.py) writes on top of its own event-specific ones, purely
# so compute_action_effectiveness() below has one shared vocabulary to
# query across all three action types at once.
ACTION_EVENT_TYPES = ["action_call", "action_message", "action_meeting"]


async def compute_action_effectiveness(
    db: AsyncSession, organization_id: str
) -> ActionEffectivenessResponse:
    """Execution-engine round — "did this ACTION lead to a RESULT," per
    action type, no ML. There's no FK from an action_* entry to the
    response that (maybe) followed it — LeadActivityLog has no such column
    (see that model's own docstring) — so this infers the link the same
    way lead_response_state already does elsewhere: by comparing
    timestamps, not by an explicit relationship.

    Simplification, disclosed: rather than pairing every individual action
    with whichever specific response came right after it (a lead can have
    several actions of the same type over its lifetime), this asks one
    coarser question per lead per action type — "after the *last* time
    this action type ran on this lead, did it ever show interest, or has
    it since converted?" A lead that eventually converts counts as a
    success for every action type it was ever subjected to, not just the
    final one — there's no way to attribute a conversion to one specific
    past action without a real link, so this doesn't pretend to. Same
    "known approximation" spirit as money_saved_today's own disclosed
    proxy (workday.py).

    Two queries regardless of org size: one LeadActivityLog scan
    (action_call/action_message/action_meeting/lead_interested, all time —
    no window, same precedent compute_conversion_insights() already sets
    for a signal this function itself feeds into via compute_lead_score()),
    one Lead status check scoped to just the leads that scan turned up.
    Each rate is None (not 0.0) until at least one lead has that action
    type at all — "no data" isn't the same claim as "0% success," same
    rule ConversionInsightsResponse's own fields already follow."""
    rows_stmt = select(
        LeadActivityLog.lead_id, LeadActivityLog.event_type, LeadActivityLog.created_at
    ).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type.in_(ACTION_EVENT_TYPES + ["lead_interested"]),
    )
    rows = (await db.execute(rows_stmt)).all()

    latest_action_at: dict[tuple, datetime] = {}
    lead_ids_by_action_type: dict[str, set] = {event_type: set() for event_type in ACTION_EVENT_TYPES}
    latest_interested_at: dict = {}

    for row in rows:
        if row.event_type == "lead_interested":
            current = latest_interested_at.get(row.lead_id)
            if current is None or row.created_at > current:
                latest_interested_at[row.lead_id] = row.created_at
            continue
        lead_ids_by_action_type[row.event_type].add(row.lead_id)
        key = (row.lead_id, row.event_type)
        current = latest_action_at.get(key)
        if current is None or row.created_at > current:
            latest_action_at[key] = row.created_at

    all_lead_ids = set().union(*lead_ids_by_action_type.values()) if rows else set()
    converted_lead_ids: set = set()
    if all_lead_ids:
        converted_stmt = select(Lead.id).where(
            Lead.id.in_(all_lead_ids), Lead.status == "converted"
        )
        converted_lead_ids = set((await db.execute(converted_stmt)).scalars().all())

    def success_rate(event_type: str) -> float | None:
        lead_ids = lead_ids_by_action_type[event_type]
        if not lead_ids:
            return None
        successes = 0
        for lead_id in lead_ids:
            if lead_id in converted_lead_ids:
                successes += 1
                continue
            interested_at = latest_interested_at.get(lead_id)
            if interested_at is not None and interested_at > latest_action_at[(lead_id, event_type)]:
                successes += 1
        return round(successes / len(lead_ids) * 100, 1)

    return ActionEffectivenessResponse(
        call_success_rate=success_rate("action_call"),
        message_success_rate=success_rate("action_message"),
        meeting_success_rate=success_rate("action_meeting"),
    )


def _clamp_adaptive_weight(rate: float, baseline: float) -> float:
    """compute_adaptive_weights()'s own multiplier formula: how much better
    (or worse) this signal value's own conversion rate is than the
    baseline it's compared against, clamped to the prompt's own
    [_ADAPTIVE_WEIGHT_MIN, _ADAPTIVE_WEIGHT_MAX] range. 1.0 (unweighted)
    whenever the baseline itself is 0 — nothing to meaningfully compare
    against yet."""
    if baseline <= 0:
        return 1.0
    return round(max(_ADAPTIVE_WEIGHT_MIN, min(_ADAPTIVE_WEIGHT_MAX, rate / baseline)), 2)


async def compute_adaptive_weights(
    db: AsyncSession, organization_id: str, *, action_effectiveness: ActionEffectivenessResponse
) -> dict[str, float]:
    """Adaptive Scoring Weights (Task 1, Adaptive Intelligence round) —
    mines the last _ADAPTIVE_WEIGHTS_WINDOW_DAYS (30) of real lead_won/
    lead_lost outcomes for which signal VALUES (not just "the one best
    industry" the way ConversionInsightsResponse's own best_industry
    already does) actually correlate with winning, and turns each into a
    multiplier compute_lead_score() applies to its own matching bonus —
    see that function's own docstring for exactly which ones. No ML: every
    weight is a plain "this value's own win rate, divided by a baseline
    win rate" ratio, clamped to a bounded range, same deterministic-rules
    style as every other compute_*() function in this module.

    Five signal families, each needing _ADAPTIVE_WEIGHTS_MIN_SAMPLE_SIZE
    real outcomes before it's trusted with its own key at all (a value with
    too few outcomes is silently omitted, not defaulted to 1.0 — omission
    IS the "no opinion yet" signal compute_lead_score()'s own dict.get(...,
    1.0) fallback already reads correctly):
      industry:{value} / company_size:{value} — this value's own win rate
        vs. the overall win rate across every outcome in the window.
      action:{action_type} — reuses the caller's own already-computed
        ActionEffectivenessResponse (score_leads() computes one per batch
        regardless) against the mean of whichever rates are real, no
        second query.
      fast_response — win rate among outcomes whose own response arrived
        under _FAST_RESPONSE_MINUTES, vs. the overall win rate.
      high_risk — win rate among outcomes whose own time-to-close exceeded
        _ADAPTIVE_HIGH_RISK_DAYS_TO_OUTCOME days (see that constant's own
        comment for why this, not deal_risk_level itself, is the proxy),
        vs. the overall win rate.

    Returns {} (compute_lead_score() then rescales nothing — every
    .get(..., 1.0) falls back to unweighted) whenever the org has no
    lead_won/lead_lost outcomes at all in the window yet. Three queries of
    its own regardless of org size: one outcome scan, one Lead row-fetch
    for enrichment_data, one response-timing scan scoped to just those
    leads."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=_ADAPTIVE_WEIGHTS_WINDOW_DAYS)

    outcomes_stmt = select(
        LeadActivityLog.lead_id, LeadActivityLog.event_type, LeadActivityLog.duration_seconds
    ).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type.in_(("lead_won", "lead_lost")),
        LeadActivityLog.created_at >= window_start,
    )
    outcome_rows = (await db.execute(outcomes_stmt)).all()
    if not outcome_rows:
        return {}

    won_ids: set = set()
    lost_ids: set = set()
    days_to_outcome_by_lead: dict = {}
    for row in outcome_rows:
        bucket = won_ids if row.event_type == "lead_won" else lost_ids
        bucket.add(row.lead_id)
        if row.duration_seconds is not None:
            days_to_outcome_by_lead[row.lead_id] = row.duration_seconds / 86400

    outcome_lead_ids = won_ids | lost_ids
    baseline_rate = len(won_ids) / len(outcome_lead_ids)

    leads_stmt = select(Lead).where(Lead.id.in_(outcome_lead_ids))
    outcome_leads = (await db.execute(leads_stmt)).scalars().all()

    response_stmt = select(LeadActivityLog.lead_id, LeadActivityLog.duration_seconds).where(
        LeadActivityLog.lead_id.in_(outcome_lead_ids),
        LeadActivityLog.event_type.in_(list(RESPONSE_STATE_BY_EVENT_TYPE)),
        LeadActivityLog.duration_seconds.isnot(None),
    )
    response_rows = (await db.execute(response_stmt)).all()
    fast_response_lead_ids = {
        row.lead_id for row in response_rows if row.duration_seconds / 60 < _FAST_RESPONSE_MINUTES
    }

    won_by_value: dict[str, dict[str, int]] = {"industry": {}, "company_size": {}}
    total_by_value: dict[str, dict[str, int]] = {"industry": {}, "company_size": {}}
    high_risk_won = 0
    high_risk_total = 0
    for lead in outcome_leads:
        is_won = lead.id in won_ids
        if lead.enrichment_data:
            for dimension in ("industry", "company_size"):
                value = lead.enrichment_data.get(dimension)
                if not value:
                    continue
                total_by_value[dimension][value] = total_by_value[dimension].get(value, 0) + 1
                if is_won:
                    won_by_value[dimension][value] = won_by_value[dimension].get(value, 0) + 1

        days_to_outcome = days_to_outcome_by_lead.get(lead.id)
        if days_to_outcome is not None and days_to_outcome > _ADAPTIVE_HIGH_RISK_DAYS_TO_OUTCOME:
            high_risk_total += 1
            if is_won:
                high_risk_won += 1

    weights: dict[str, float] = {}

    for dimension in ("industry", "company_size"):
        for value, total in total_by_value[dimension].items():
            if total < _ADAPTIVE_WEIGHTS_MIN_SAMPLE_SIZE:
                continue
            won = won_by_value[dimension].get(value, 0)
            weights[f"{dimension}:{value}"] = _clamp_adaptive_weight(won / total, baseline_rate)

    if high_risk_total >= _ADAPTIVE_WEIGHTS_MIN_SAMPLE_SIZE:
        weights["high_risk"] = _clamp_adaptive_weight(high_risk_won / high_risk_total, baseline_rate)

    fast_response_in_scope = fast_response_lead_ids & outcome_lead_ids
    if len(fast_response_in_scope) >= _ADAPTIVE_WEIGHTS_MIN_SAMPLE_SIZE:
        fast_response_won = len(fast_response_in_scope & won_ids)
        weights["fast_response"] = _clamp_adaptive_weight(
            fast_response_won / len(fast_response_in_scope), baseline_rate
        )

    action_rates = {
        "call_now": action_effectiveness.call_success_rate,
        "send_message": action_effectiveness.message_success_rate,
        "schedule_meeting": action_effectiveness.meeting_success_rate,
    }
    real_action_rates = [rate for rate in action_rates.values() if rate is not None]
    if real_action_rates:
        action_baseline = sum(real_action_rates) / len(real_action_rates)
        for action_type, rate in action_rates.items():
            if rate is not None:
                weights[f"action:{action_type}"] = _clamp_adaptive_weight(rate, action_baseline)

    return weights


# Real-Time Learning Engine (Task 1, final round) — a process-local,
# in-memory companion to compute_adaptive_weights()'s own 30-day DB-backed
# batch computation, keyed by organization_id then by the same signal keys
# that function already produces ("industry:X", "action:X", "fast_response",
# ...). Deliberately NOT a database table: the prompt's own ask is "store
# in-memory or cache (no DB required)" for a fast, incremental nudge on
# every relevant event, not a durable record. Disclosed limitation: this
# dict is per-process (a multi-worker deployment has each worker learning
# independently, and a restart clears it entirely) — compute_adaptive_
# weights() remains the actual source of truth compute_lead_score() reads
# every request; this cache is merged on top of (not instead of) that
# batch result in score_leads() below, so a worker that hasn't seen an
# event yet still falls back to the real, DB-backed figure.
_REALTIME_WEIGHTS_CACHE: dict[str, dict[str, float]] = {}

# The prompt's own literal EMA split (new = old*0.9 + observed*0.1) — a
# small alpha so one single event nudges a weight rather than swinging it,
# consistent with compute_adaptive_weights()'s own _ADAPTIVE_WEIGHTS_
# MIN_SAMPLE_SIZE guard against over-reacting to one data point.
_REALTIME_EMA_ALPHA = 0.1
# observed_value inputs for each event type's own nudge — landing inside
# the same [_ADAPTIVE_WEIGHT_MIN, _ADAPTIVE_WEIGHT_MAX] range those
# weights are clamped to, so the EMA converges toward a sensible steady
# state rather than an arbitrary one.
_REALTIME_OBSERVED_WON = 1.5
_REALTIME_OBSERVED_LOST = 0.8
_REALTIME_OBSERVED_INTERESTED = 1.3
_REALTIME_OBSERVED_ACTIVITY = 1.0


def get_realtime_adaptive_weights(organization_id: str) -> dict[str, float]:
    """Read-side of the Real-Time Learning Engine (Task 1) — whatever this
    process has nudged for this org so far via update_adaptive_weights_
    realtime() below. {} for an org this process hasn't seen an event for
    yet (not an error — just "no realtime signal, fall back to the batch
    figure")."""
    return dict(_REALTIME_WEIGHTS_CACHE.get(organization_id, {}))


def update_adaptive_weights_realtime(event: dict) -> None:
    """Real-Time Learning Engine (Task 1, final round) — incrementally
    nudges the in-memory realtime weights cache via a plain exponential
    moving average (see _REALTIME_EMA_ALPHA's own comment for the exact
    formula), instead of compute_adaptive_weights()'s own full 30-day
    batch recompute. Synchronous and pure in-memory — no DB access, no
    await needed, safe to call directly from any request handler that
    just logged one of the four trigger events.

    `event` is a plain dict (not a schema — this never crosses a network
    boundary) with at least `type` (one of "lead_won"/"lead_lost"/
    "lead_interested"/"message_sent") and `organization_id`; a call
    missing either is silently a no-op. Each event type nudges whichever
    keys it actually has signal for — a caller with no enrichment_data on
    hand, say, simply omits `industry`/`company_size` and only the keys it
    does supply get touched:
      lead_won / lead_lost — nudges industry:{industry}, company_size:
        {company_size}, action:{action_type} (whichever of the three are
        present in `event`) toward _REALTIME_OBSERVED_WON/_LOST.
      lead_interested — nudges "fast_response" toward _REALTIME_OBSERVED_
        INTERESTED when `event["response_time_minutes"]` is under
        _FAST_RESPONSE_MINUTES, and action:{action_type} the same way if
        present.
      message_sent — nudges action:send_message toward the neutral
        _REALTIME_OBSERVED_ACTIVITY (1.0): a message going out is real
        activity but carries no win/loss verdict of its own yet."""
    event_type = event.get("type")
    organization_id = event.get("organization_id")
    if not event_type or not organization_id:
        return

    cache = _REALTIME_WEIGHTS_CACHE.setdefault(organization_id, {})

    def nudge(key: str, observed_value: float) -> None:
        old_weight = cache.get(key, 1.0)
        new_weight = old_weight * (1 - _REALTIME_EMA_ALPHA) + observed_value * _REALTIME_EMA_ALPHA
        cache[key] = round(max(_ADAPTIVE_WEIGHT_MIN, min(_ADAPTIVE_WEIGHT_MAX, new_weight)), 4)

    if event_type in ("lead_won", "lead_lost"):
        observed = _REALTIME_OBSERVED_WON if event_type == "lead_won" else _REALTIME_OBSERVED_LOST
        if event.get("industry"):
            nudge(f"industry:{event['industry']}", observed)
        if event.get("company_size"):
            nudge(f"company_size:{event['company_size']}", observed)
        if event.get("action_type"):
            nudge(f"action:{event['action_type']}", observed)
    elif event_type == "lead_interested":
        response_time_minutes = event.get("response_time_minutes")
        if response_time_minutes is not None and response_time_minutes < _FAST_RESPONSE_MINUTES:
            nudge("fast_response", _REALTIME_OBSERVED_INTERESTED)
        if event.get("action_type"):
            nudge(f"action:{event['action_type']}", _REALTIME_OBSERVED_INTERESTED)
    elif event_type == "message_sent":
        nudge("action:send_message", _REALTIME_OBSERVED_ACTIVITY)


# Revenue-loop round — the same three action_* event types
# compute_action_effectiveness() above reads, just relabeled to
# compute_revenue_attribution()'s own plain-noun vocabulary (its
# revenue_by_action keys) instead of that function's raw event_type
# strings.
REVENUE_ACTION_LABEL_BY_EVENT_TYPE = {
    "action_call": "call",
    "action_message": "message",
    "action_meeting": "meeting",
}


async def compute_revenue_attribution(
    db: AsyncSession, organization_id: str
) -> RevenueAttributionResponse:
    """Execution-engine round's compute_action_effectiveness() answers "does
    this action tend to work" (a success *rate*, out of 100); this closes
    the loop the rest of the way — ACTION -> RESPONSE -> CONVERSION ->
    MONEY — by answering "how much actual revenue came from it" (a real R$
    total).

    For every converted lead, credits its *entire* estimated_value
    (get_lead_estimated_value(), enrichment.py — no partial split across
    several actions, no ML) to exactly one bucket: the action type of the
    LAST action_call/action_message/action_meeting event logged for that
    lead at or before its own conversion. There's no converted_at column
    (see Lead's own docstring), so "before conversion" is approximated by
    updated_at — the same disclosed proxy compute_action_effectiveness()
    already uses for its own "before/after" comparisons, not a new
    approximation invented here. A converted lead with no qualifying
    action_* event at all (e.g. converted through a flow this round
    doesn't instrument) simply isn't credited to any action bucket — a real
    gap, not something to fake an attribution for; its value still counts
    toward revenue_by_industry/revenue_by_company_size below, since those
    two don't depend on the action link at all.

    Winner Pattern Replication (Task 4, revenue-maximization round) adds
    top_combination: the single "action | industry | company_size" string
    (e.g. "call | Technology | 500+" — " | " chosen over "+" as the
    delimiter since a company_size value like "500+" already contains a
    literal "+") with the most attributed revenue behind it. Unlike
    revenue_by_industry/revenue_by_company_size, a combination DOES need
    the action link — "action" is literally part of the key — so a
    converted lead with no qualifying action_* event never contributes one,
    same as revenue_by_action itself.

    Two queries regardless of org size: one Lead scan (converted, this
    org), one LeadActivityLog scan scoped to just those leads' ids."""
    converted_stmt = select(Lead).where(
        Lead.organization_id == organization_id,
        Lead.status == "converted",
        Lead.deleted_at.is_(None),
    )
    converted_leads = (await db.execute(converted_stmt)).scalars().all()

    revenue_by_action = {"call": 0.0, "message": 0.0, "meeting": 0.0}
    revenue_by_industry: dict[str, float] = {}
    revenue_by_company_size: dict[str, float] = {}
    revenue_by_combination: dict[str, float] = {}

    if not converted_leads:
        return RevenueAttributionResponse(
            revenue_by_action=revenue_by_action,
            revenue_by_industry=revenue_by_industry,
            revenue_by_company_size=revenue_by_company_size,
        )

    lead_ids = [lead.id for lead in converted_leads]
    actions_stmt = select(
        LeadActivityLog.lead_id, LeadActivityLog.event_type, LeadActivityLog.created_at
    ).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.lead_id.in_(lead_ids),
        LeadActivityLog.event_type.in_(ACTION_EVENT_TYPES),
    )
    action_rows = (await db.execute(actions_stmt)).all()

    leads_by_id = {lead.id: lead for lead in converted_leads}
    last_action_event_type: dict = {}
    last_action_at: dict = {}
    for row in action_rows:
        lead = leads_by_id[row.lead_id]
        if row.created_at > lead.updated_at:
            continue  # logged after conversion — not what led to it
        current = last_action_at.get(row.lead_id)
        if current is None or row.created_at > current:
            last_action_at[row.lead_id] = row.created_at
            last_action_event_type[row.lead_id] = row.event_type

    for lead in converted_leads:
        value = get_lead_estimated_value(lead)
        if value <= 0:
            continue

        event_type = last_action_event_type.get(lead.id)
        label = None
        if event_type is not None:
            label = REVENUE_ACTION_LABEL_BY_EVENT_TYPE[event_type]
            revenue_by_action[label] += value

        if lead.enrichment_data:
            industry = lead.enrichment_data.get("industry")
            company_size = lead.enrichment_data.get("company_size")
            if industry:
                revenue_by_industry[industry] = revenue_by_industry.get(industry, 0.0) + value
            if company_size:
                revenue_by_company_size[company_size] = (
                    revenue_by_company_size.get(company_size, 0.0) + value
                )
            if label and industry and company_size:
                combination = f"{label} | {industry} | {company_size}"
                revenue_by_combination[combination] = (
                    revenue_by_combination.get(combination, 0.0) + value
                )

    top_combination = top_revenue_bucket(revenue_by_combination) if revenue_by_combination else None

    return RevenueAttributionResponse(
        revenue_by_action=revenue_by_action,
        revenue_by_industry=revenue_by_industry,
        revenue_by_company_size=revenue_by_company_size,
        top_combination=top_combination,
    )


def top_revenue_bucket(revenue_by_bucket: dict[str, float]) -> str | None:
    """The single highest-revenue key in any of
    RevenueAttributionResponse's three breakdown dicts (revenue_by_action/
    revenue_by_industry/revenue_by_company_size) — None while every bucket
    is still 0.0 (or the dict is empty), so compute_lead_score()'s revenue
    bonus, compute_action_type_and_urgency()'s strategy shift, and GET
    /workday/summary's own top_revenue_* fields all stay silent until
    there's real attributed money to point to, rather than an arbitrary
    tie-break on an empty signal."""
    if not revenue_by_bucket or not any(revenue_by_bucket.values()):
        return None
    return max(revenue_by_bucket, key=revenue_by_bucket.get)


async def compute_revenue_summary(
    db: AsyncSession, organization_id: str, *, today_start: datetime
) -> tuple[float, float | None]:
    """(revenue_generated_today, avg_revenue_per_conversion) — the two
    GET /workday/performance asks for that compute_revenue_attribution()
    doesn't itself carry (that function's own shape is a fixed three-bucket
    breakdown, not a running total or an average). revenue_generated_today
    sums estimated_value for every lead with a "lead_won" LeadActivityLog
    entry (the precise conversion-moment marker PATCH /leads/{id}/status
    writes, leads.py — the same event compute_conversion_insights() already
    reads for avg_time_to_close_days) created today. avg_revenue_per_
    conversion is the all-time mean estimated_value across every converted
    lead this org has ever had (None, not 0.0, when there isn't one yet —
    same "no signal" rule this file's other aggregates already follow),
    regardless of whether the conversion happened today.

    Two queries: one full converted-leads scan (all time, reused for both
    the average and revenue_generated_today's own value lookups), one
    lead_won id scan (today only)."""
    converted_stmt = select(Lead).where(
        Lead.organization_id == organization_id,
        Lead.status == "converted",
        Lead.deleted_at.is_(None),
    )
    converted_leads = (await db.execute(converted_stmt)).scalars().all()
    if not converted_leads:
        return 0.0, None

    values_by_lead_id = {lead.id: get_lead_estimated_value(lead) for lead in converted_leads}
    avg_revenue_per_conversion = round(sum(values_by_lead_id.values()) / len(values_by_lead_id), 2)

    won_today_stmt = select(LeadActivityLog.lead_id).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type == "lead_won",
        LeadActivityLog.created_at >= today_start,
    )
    won_today_ids = set((await db.execute(won_today_stmt)).scalars().all())
    revenue_generated_today = sum(values_by_lead_id.get(lead_id, 0.0) for lead_id in won_today_ids)

    return revenue_generated_today, avg_revenue_per_conversion


async def _compute_daily_target_revenue(db: AsyncSession, organization_id: str, now: datetime) -> float:
    """Shared by compute_acceleration_mode() and compute_hunter_mode()
    (Elite round, Task 7) — the same 7-day "lead_won" average GET
    /workday/target's own _compute_daily_target_revenue() (workday.py)
    computes, kept as its own independent copy in this module for the same
    reason _RISK_LEVEL_ORDER is duplicated rather than imported (see that
    constant's own comment): workday_engine.py imports FROM scoring.py, so
    the reverse import would be circular. One lead_won id scan (7-day
    window) plus its leads' own row-fetch."""
    target_cutoff = now - timedelta(days=_ACCELERATION_MODE_TARGET_WINDOW_DAYS)
    won_ids_stmt = (
        select(LeadActivityLog.lead_id)
        .distinct()
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type == "lead_won",
            LeadActivityLog.created_at >= target_cutoff,
        )
    )
    won_ids = (await db.execute(won_ids_stmt)).scalars().all()
    if not won_ids:
        return 0.0
    won_leads_stmt = select(Lead).where(Lead.id.in_(won_ids))
    won_leads = (await db.execute(won_leads_stmt)).scalars().all()
    return sum(get_lead_estimated_value(lead) for lead in won_leads) / _ACCELERATION_MODE_TARGET_WINDOW_DAYS


async def compute_acceleration_mode(db: AsyncSession, organization_id: str) -> bool:
    """Revenue Acceleration Mode's own trigger (Task 3, revenue-
    maximization round; formula tightened in the Ultimate-Sales-OS round,
    Task 5) — true whenever current_expected sits below
    _ACCELERATION_MODE_RATIO_THRESHOLD (70%) of daily_target_revenue, i.e.
    the org is on pace for meaningfully less than its target rather than
    merely some fixed dollar amount short of it (the round's own literal
    ask: `current_expected < target * 0.7`, replacing the previous
    absolute-gap check). Deliberately a cheap, independent approximation, NOT the same precise
    gap GET /workday/target reports (see that endpoint's own
    daily_target_revenue/current_expected, workday.py, for the
    authoritative figure driving the frontend's banner): computing the
    precise version here would need rank_leads_by_priority()'s own fully-
    scored candidate pool, but rank_leads_by_priority() is itself the
    function that calls score_leads() — the one place this flag actually
    needs to reach — so a direct dependency would be circular.

    daily_target_revenue below is the same 7-day "lead_won" average that
    endpoint also computes. current_expected is a lighter stand-in:
    win_probability computed fresh (compute_win_probability(), assuming no
    recent manual activity or task completion — checking those here would
    mean re-deriving most of score_leads() itself) for just the leads due
    today or already overdue, summed. Rougher than the authoritative
    figure, but the same "close enough to act on" bar this codebase's
    other proxies already accept (see money_saved_today's own docstring,
    workday.py).

    Two queries: one lead_won id scan (7-day window) plus its leads' own
    row-fetch for daily_target_revenue, one due-today/overdue Lead row-
    fetch for current_expected."""
    now = datetime.now(timezone.utc)
    today_end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    daily_target_revenue = await _compute_daily_target_revenue(db, organization_id, now)

    due_stmt = select(Lead).where(
        Lead.organization_id == organization_id,
        Lead.deleted_at.is_(None),
        Lead.status.notin_(("converted", "lost")),
        Lead.next_action_due_at.isnot(None),
        Lead.next_action_due_at < today_end,
    )
    due_leads = (await db.execute(due_stmt)).scalars().all()
    current_expected = 0
    for lead in due_leads:
        win_probability = compute_win_probability(
            lead, has_recent_manual_activity=False, task_completed_recently=False, now=now
        )
        current_expected += round(get_lead_estimated_value(lead) * win_probability / 100)

    if daily_target_revenue <= 0:
        return False
    return current_expected < daily_target_revenue * _ACCELERATION_MODE_RATIO_THRESHOLD


async def compute_hunter_mode(db: AsyncSession, organization_id: str) -> bool:
    """Hunter Mode (Elite round, Task 7) — a much lower bar than Revenue
    Acceleration Mode's own gap check above: true whenever the org's
    entire open pipeline (every non-terminal lead's own win_probability-
    weighted expected_value, summed) is worth less than half a single
    day's own revenue target (_HUNTER_MODE_PIPELINE_RATIO_THRESHOLD,
    reusing the same daily_target_revenue calculation compute_acceleration_
    mode() already does). This fires only when there's structurally not
    enough in the pipeline at all — a distinct, complementary signal from
    Acceleration Mode's own "today's leads are behind pace." Deliberately
    a cheap approximation, same "close enough to act on" bar every other
    org-wide flag in this module already accepts. Returns False whenever
    there's no won-lead history yet to set a target from (same "no
    signal, no false alarm" rule compute_acceleration_mode() follows).
    Two queries: the shared daily-target-revenue calculation, plus one
    full open-pipeline row-fetch."""
    now = datetime.now(timezone.utc)
    daily_target_revenue = await _compute_daily_target_revenue(db, organization_id, now)
    if daily_target_revenue <= 0:
        return False

    pipeline_stmt = select(Lead).where(
        Lead.organization_id == organization_id,
        Lead.deleted_at.is_(None),
        Lead.status.notin_(("converted", "lost")),
    )
    pipeline_leads = (await db.execute(pipeline_stmt)).scalars().all()
    pipeline_value = 0
    for lead in pipeline_leads:
        win_probability = compute_win_probability(
            lead, has_recent_manual_activity=False, task_completed_recently=False, now=now
        )
        pipeline_value += round(get_lead_estimated_value(lead) * win_probability / 100)

    return pipeline_value < daily_target_revenue * _HUNTER_MODE_PIPELINE_RATIO_THRESHOLD


def build_priority_reason(
    lead: Lead,
    *,
    estimated_value: int,
    win_probability: int,
    days_idle: int,
    is_overdue: bool,
    is_low_potential: bool = False,
    is_high_opportunity_cost: bool = False,
) -> str:
    """"Why this lead?" (feedback-loop round) — one ready-to-render
    sentence explaining the same signals score_leads() already computed for
    this lead, composed from whichever of them are actually notable rather
    than always listing every factor. Pure/no DB access, same reasoning
    style as compute_next_best_action().

    is_low_potential (Autonomous-sales-OS round's pruning flag, threaded
    through from score_leads() — same criteria as compute_lead_score()'s
    own pruning penalty) always wins the sentence outright when true: a
    lead with no real revenue potential left doesn't need its other,
    now-moot signals (value/probability/idle) listed alongside it.
    is_high_opportunity_cost (revenue-maximization round's Opportunity Cost
    Engine, Task 1) is checked next, same "outright override" treatment —
    it's a stronger, more actionable signal than any of the composed
    clauses below.

    "Priority Explanation" humanization (Elite round, Task 10): whenever
    there's a real revenue signal (estimated_value > 0 — i.e. the lead has
    at least been enriched), value and win_probability are always narrated
    together as one sentence ("Esse lead pode gerar R$ X com Y% de
    chance...") rather than only mentioned past a "high value" threshold
    the way the old clause-list style did — the prompt's own literal
    example. An idle/overdue clause is appended with "mas" when present.
    Falls back to the previous terse clause-list style only when there's no
    value signal to narrate at all (an unenriched lead)."""
    if lead.status == "converted":
        return "Lead convertido — nada a fazer."
    if lead.status == "lost":
        return "Lead perdido — nada a fazer."
    if is_low_potential:
        return "Lead sem potencial de receita — recomendado descarte."
    if is_high_opportunity_cost:
        return "Você está deixando de focar em leads que podem gerar mais R$."

    idle_clause: str | None = None
    if is_overdue:
        idle_clause = "está com uma tarefa atrasada"
    elif days_idle > _FOLLOW_UP_ESCALATION_IDLE_DAYS:
        idle_clause = f"está parado há {days_idle} dias"

    if estimated_value > 0:
        narrative = f"Esse lead pode gerar R$ {format_brl(estimated_value)} com {win_probability}% de chance"
        if idle_clause:
            return f"{narrative}, mas {idle_clause}."
        return f"{narrative}."

    clauses: list[str] = []
    if win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
        clauses.append(f"alta probabilidade ({win_probability}%)")
    elif win_probability < _LOW_WIN_PROBABILITY_THRESHOLD:
        clauses.append(f"baixa probabilidade ({win_probability}%)")
    if idle_clause:
        clauses.append(idle_clause)

    if not clauses:
        return "Lead em acompanhamento normal, sem sinais fortes de prioridade no momento."

    sentence = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + f" e {clauses[-1]}"
    return sentence[0].upper() + sentence[1:] + "."


def compute_deal_risk(
    lead: Lead, *, expected_value: int, win_probability: int, is_overdue: bool, now: datetime
) -> tuple[str, str]:
    """AI Deal Coach round — a plain rule table (no ML/external AI calls)
    collapsing money/probability/activity recency into one at-a-glance
    risk_level plus a short reason sentence. expected_value/win_probability
    aren't columns on Lead itself (they're computed earlier in the same
    score_leads() pass — compute_win_probability/get_lead_estimated_value),
    so they're passed in rather than recomputed here; idle_days is derived
    from lead.updated_at, same "cheap, pure, independently derived"
    precedent compute_win_probability's own is_overdue/days_idle already
    set. Converted/lost leads are always "low" — nothing left to lose, so
    nothing left to be at risk.

    Ordered highest-severity-first, same style as compute_next_best_action's
    own decision tree:
      CRITICAL: a big deal (>= HIGH_VALUE_LEAD_THRESHOLD) that's either
        overdue or idle for over _DEAL_RISK_CRITICAL_IDLE_DAYS.
      HIGH: a big deal that still looks winnable
        (win_probability >= _DEAL_RISK_HIGH_WIN_PROBABILITY) but idle for
        over _DEAL_RISK_HIGH_IDLE_DAYS.
      MEDIUM: idle for over _DEAL_RISK_MEDIUM_IDLE_DAYS, or overdue,
        regardless of value/probability — everything CRITICAL/HIGH didn't
        already catch.
      LOW: everything else.
    """
    if lead.status in ("converted", "lost"):
        return "low", "Lead já resolvido — nada em jogo."

    idle_days = (now - lead.updated_at).days
    is_big_deal = expected_value >= HIGH_VALUE_LEAD_THRESHOLD

    if is_big_deal and (is_overdue or idle_days > _DEAL_RISK_CRITICAL_IDLE_DAYS):
        cause = "com tarefa atrasada" if is_overdue else f"parado há {idle_days} dias"
        return "critical", (
            f"Negócio de R$ {format_brl(expected_value)} {cause} — risco de perda iminente."
        )

    if (
        is_big_deal
        and win_probability >= _DEAL_RISK_HIGH_WIN_PROBABILITY
        and idle_days > _DEAL_RISK_HIGH_IDLE_DAYS
    ):
        return "high", (
            f"Negócio de R$ {format_brl(expected_value)} com {win_probability}% de chance de "
            f"fechar, mas sem contato há {idle_days} dias."
        )

    if idle_days > _DEAL_RISK_MEDIUM_IDLE_DAYS or is_overdue:
        reason = "Tarefa atrasada — agende um contato." if is_overdue else (
            f"Sem atividade há {idle_days} dias."
        )
        return "medium", reason

    return "low", "Sob controle por enquanto."


def compute_action_type_and_urgency(
    lead: Lead,
    risk_level: str,
    *,
    expected_value: int = 0,
    top_revenue_action: str | None = None,
    acceleration_mode: bool = False,
    win_probability: int = 0,
    hunter_mode: bool = False,
    aggression_level: str | None = None,
    global_strategy_focus: str | None = None,
) -> tuple[str | None, str | None]:
    """AI Deal Coach's action recommendation — collapses risk_level (plus
    the lead's own status) into one concrete next action + urgency tag for
    the frontend's call-to-action button (LeadCard), distinct from
    next_best_action's full sentence. status is checked before risk_level:
    a lost lead always gets "drop_lead" regardless of risk (compute_deal_risk
    already returns "low" for it, so risk_level alone can't distinguish
    "lost" from "healthy"); a converted lead gets no action at all, same
    "nothing left to do" rule next_best_action already follows.

    Revenue-loop round's strategy shift (Task 3): once compute_revenue_
    attribution() shows one channel is actually generating the most real
    money org-wide, the recommendation leans toward repeating it —
    expressed here (not in compute_next_best_action's own text-sentence
    tree, which never deals in "call_now"/"schedule_meeting" literals to
    begin with) since this is the one function whose entire job is picking
    between those exact three action types. The shift never touches the
    "critical" tier's own call_now above — that is an emergency escalation,
    not a channel preference, so it stays absolute. Below it: if "call" is
    the top earner, every remaining lead is pushed toward call_now
    regardless of what risk_level alone would have picked; if "meeting" is
    the top earner, the same push toward schedule_meeting applies, but only
    for a lead already worth >= HIGH_VALUE_LEAD_THRESHOLD (the prompt's own
    "for high-value leads" qualifier — a small deal doesn't warrant the
    extra weight of booking a meeting just because meetings convert well
    elsewhere). Urgency is left exactly as risk_level would have set it in
    every case: this shift changes WHICH channel to use, never how urgently.

    Revenue Acceleration Mode (Task 3, revenue-maximization round): once
    compute_acceleration_mode() reports the org is meaningfully behind its
    daily revenue target, every remaining non-critical, non-terminal lead
    that's ALSO already likely to close (win_probability >=
    _HIGH_WIN_PROBABILITY_THRESHOLD — Ultimate-Sales-OS round's own gate,
    Task 2: "close it now" only makes sense for a deal that's actually
    close) is forced to call_now at "high" urgency — checked right after the
    "critical" tier's own call_now above (still absolute: an emergency
    escalation outranks a blanket policy) but before the revenue-
    attribution strategy shift, since "call everything now, we're behind"
    is a stronger, more urgent signal than a learned channel preference.

    Hunter Mode (Elite round, Task 7): once compute_hunter_mode() reports
    the org's whole open pipeline is running structurally thin, a fresh
    ("new") lead already worth >= HIGH_VALUE_LEAD_THRESHOLD is forced to
    call_now too — checked right after Acceleration Mode's own forced
    call_now (a thin pipeline is a real but less urgent problem than being
    behind on today's actionable revenue) and, unlike that check, scoped to
    new leads specifically: the whole point of Hunter Mode is chasing fresh
    high-value opportunities before the pipeline runs any drier, not
    re-routing leads already being worked.

    Action Override Engine (Task 4, final round): aggression_level ==
    "extreme" (compute_aggression_level(), this module) forces call_now on
    every remaining non-terminal lead, checked right after the "critical"
    tier's own call_now — an org-wide emergency still outranks it, same
    "blanket policy beats a per-lead preference" precedent Acceleration
    Mode/Hunter Mode already established above, but this one outranks even
    those two: "extreme" is this system's own worst-case reading of the
    whole pipeline, a stronger signal than either. Both new params default
    to None — every existing caller that doesn't pass them (score_leads()'s
    own internal call included) gets 100% unchanged behavior; only a
    caller that has actually computed these two org-wide signals opts in.
    global_strategy_focus (compute_global_strategy()) biases the channel
    choice the same way the older top_revenue_action-based shift below
    already does, just checked first since it's the more holistic signal
    (revenue + response rate + win probability together, not revenue
    alone) — "meetings" isn't handled here (only calls/messages), so it
    falls through to the existing logic below unchanged."""
    if lead.status == "lost":
        return "drop_lead", "low"
    if lead.status == "converted":
        return None, None
    if risk_level == "critical":
        return "call_now", "immediate"
    if aggression_level == "extreme":
        return "call_now", "immediate"
    if acceleration_mode and win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
        return "call_now", "high"
    if hunter_mode and lead.status == "new" and expected_value >= HIGH_VALUE_LEAD_THRESHOLD:
        return "call_now", "high"

    urgency = "high" if risk_level == "high" else "medium" if risk_level == "medium" else "low"

    if global_strategy_focus == "calls":
        return "call_now", urgency
    if global_strategy_focus == "messages":
        return "send_message", urgency

    if top_revenue_action == "call":
        return "call_now", urgency
    if top_revenue_action == "meeting" and expected_value >= HIGH_VALUE_LEAD_THRESHOLD:
        return "schedule_meeting", urgency

    if risk_level == "high":
        return "send_message", urgency
    if risk_level == "medium":
        return "schedule_meeting", urgency
    return "monitor", urgency


def apply_strategy_override(
    response: LeadResponse,
    *,
    aggression_level: str | None = None,
    global_strategy_focus: str | None = None,
    top_revenue_action: str | None = None,
) -> LeadResponse:
    """Action Override Engine (Task 4, final round) — re-applies
    compute_action_type_and_urgency() to an already-scored LeadResponse
    with the two new org-wide signals filled in. Exists because
    compute_global_strategy()/compute_aggression_level() both need an
    already-scored `leads` list (plus response-rate/simulation figures)
    as their own inputs — they can't run *inside* score_leads() without a
    circular dependency — so this lets their result feed back into the
    recommendation as a deliberate second pass a caller opts into, rather
    than baking it into score_leads() itself (which stays 100% unchanged:
    its own internal call to compute_action_type_and_urgency() never
    passes these two params, so every existing reader of score_leads()
    keeps getting the exact same recommendation as before this function
    existed).

    Passing `response` itself as compute_action_type_and_urgency()'s own
    `lead` argument works even though that parameter is typed `Lead`:
    the function only ever reads `.status` off it, a field LeadResponse
    carries too. Reuses response.acceleration_mode/hunter_mode (both
    already on LeadResponse) rather than requiring them as new params.

    Returns a new LeadResponse (next_best_action_type/urgency updated,
    ready_to_send_message/auto_action_available re-derived to match) —
    never mutates its input, and returns the same object unchanged
    whenever neither override signal actually changes the recommendation
    (idempotent: calling this twice with the same inputs is a no-op the
    second time)."""
    action_type, action_urgency = compute_action_type_and_urgency(
        response,
        response.deal_risk_level,
        expected_value=response.expected_value,
        top_revenue_action=top_revenue_action,
        acceleration_mode=response.acceleration_mode,
        win_probability=response.win_probability,
        hunter_mode=response.hunter_mode,
        aggression_level=aggression_level,
        global_strategy_focus=global_strategy_focus,
    )
    if action_type == response.next_best_action_type and action_urgency == response.next_best_action_urgency:
        return response

    is_ready_to_send = action_type == "send_message" and response.suggested_message is not None
    return response.model_copy(
        update={
            "next_best_action_type": action_type,
            "next_best_action_urgency": action_urgency,
            "ready_to_send_message": response.suggested_message if is_ready_to_send else None,
            "auto_action_available": is_ready_to_send,
        }
    )


async def score_leads(db: AsyncSession, leads: list[Lead]) -> list[LeadResponse]:
    """Builds LeadResponse for each lead with score/score_breakdown
    overridden by compute_lead_score(), instead of the plain
    LeadResponse.model_validate(lead) every lead-returning endpoint used
    before this. Up to thirteen extra queries total (recent automation
    activity, recent manual activity, compute_conversion_insights()'s own
    two, compute_response_metrics()'s own one, compute_action_effectiveness()'s
    own two, compute_revenue_attribution()'s own two, compute_acceleration_mode()'s
    own two (revenue-maximization round), one covering both
    lead_response_state and has_pending_response/response_delay_minutes,
    plus one for days_since_last_activity) for the whole batch, regardless
    of how many leads are passed in — no N+1."""
    if not leads:
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=_RECENT_AUTOMATION_DAYS)
    lead_ids = [lead.id for lead in leads]

    # Every call site scopes `leads` to a single organization already (the
    # same invariant the automation/manual-activity queries below rely on
    # by filtering only on lead_id, not organization_id) — so the first
    # lead's organization_id is this whole batch's.
    organization_id = leads[0].organization_id
    insights = await compute_conversion_insights(db, organization_id)
    response_metrics = await compute_response_metrics(db, organization_id)
    action_effectiveness = await compute_action_effectiveness(db, organization_id)
    revenue_attribution = await compute_revenue_attribution(db, organization_id)
    top_revenue_action = top_revenue_bucket(revenue_attribution.revenue_by_action)
    top_combination = revenue_attribution.top_combination
    acceleration_mode = await compute_acceleration_mode(db, organization_id)
    hunter_mode = await compute_hunter_mode(db, organization_id)
    adaptive_weights = await compute_adaptive_weights(
        db, organization_id, action_effectiveness=action_effectiveness
    )
    # Real-Time Learning Engine (Task 1, final round) — the process-local
    # realtime cache overrides the batch figure key-for-key wherever it has
    # a fresher opinion (an event since the last 30-day recompute), and
    # falls back to the batch value everywhere else. See
    # _REALTIME_WEIGHTS_CACHE's own comment for why this, not a DB write,
    # is the source for the realtime half.
    adaptive_weights = {**adaptive_weights, **get_realtime_adaptive_weights(organization_id)}

    recent_stmt = (
        select(AutomationActivityLog.lead_id)
        .distinct()
        .where(
            AutomationActivityLog.lead_id.in_(lead_ids),
            AutomationActivityLog.created_at >= cutoff,
        )
    )
    recent_lead_ids = set((await db.execute(recent_stmt)).scalars().all())

    # One query covers both "Recent manual activity" (any event, 3-day
    # window — same cutoff as automation's, above) and "Task completed in
    # the last 24h" (task_completed events only, tighter window) — both
    # booleans are derived from this same result set in Python instead of
    # querying twice.
    manual_activity_stmt = select(
        LeadActivityLog.lead_id, LeadActivityLog.event_type, LeadActivityLog.created_at
    ).where(
        LeadActivityLog.lead_id.in_(lead_ids),
        LeadActivityLog.created_at >= cutoff,
    )
    manual_activity_rows = (await db.execute(manual_activity_stmt)).all()
    recent_manual_activity_ids = {row.lead_id for row in manual_activity_rows}

    task_completion_cutoff = now - timedelta(hours=_RECENT_TASK_COMPLETION_HOURS)
    recent_task_completed_ids = {
        row.lead_id
        for row in manual_activity_rows
        if row.event_type == "task_completed" and row.created_at >= task_completion_cutoff
    }

    # lead_response_state/has_pending_response both read the same event
    # types (plus "message_sent", needed only for the latter) all-time, not
    # a 30-day-windowed rate like compute_response_metrics() above — one
    # query covers both: each lead's most recent response-type entry (a
    # later "interested" supersedes an earlier plain "responded", etc.) and
    # its most recent "message_sent", tracked separately below.
    response_state_stmt = select(
        LeadActivityLog.lead_id,
        LeadActivityLog.event_type,
        LeadActivityLog.duration_seconds,
        LeadActivityLog.created_at,
    ).where(
        LeadActivityLog.lead_id.in_(lead_ids),
        LeadActivityLog.event_type.in_(list(RESPONSE_STATE_BY_EVENT_TYPE) + ["message_sent"]),
    )
    response_state_rows = (await db.execute(response_state_stmt)).all()
    latest_response_by_lead = {}
    latest_message_sent_by_lead = {}
    for row in response_state_rows:
        bucket = (
            latest_message_sent_by_lead if row.event_type == "message_sent" else latest_response_by_lead
        )
        current = bucket.get(row.lead_id)
        if current is None or row.created_at > current.created_at:
            bucket[row.lead_id] = row

    # days_since_last_activity (sales-operating-system round) — the most
    # recent LeadActivityLog row of ANY kind per lead, all time. Distinct
    # from the two dicts above (which only track specific event types) and
    # from days_idle (lead.updated_at-derived) below — see
    # LeadResponse.days_since_last_activity's own docstring for why.
    last_activity_stmt = (
        select(LeadActivityLog.lead_id, func.max(LeadActivityLog.created_at))
        .where(LeadActivityLog.lead_id.in_(lead_ids))
        .group_by(LeadActivityLog.lead_id)
    )
    last_activity_by_lead = dict((await db.execute(last_activity_stmt)).all())

    # Opportunity Cost Engine (Task 1, revenue-maximization round) — needs
    # every lead's own win_probability/expected_value to find this batch's
    # single highest expected_value before the main loop below can compute
    # each lead's opportunity_cost against it. Both are pure, cheap
    # functions (no DB access), so precomputing them here just means the
    # main loop reads from these dicts instead of recomputing the same
    # values a second time.
    win_probability_by_lead_id: dict = {}
    expected_value_by_lead_id: dict = {}
    for lead in leads:
        win_probability = compute_win_probability(
            lead,
            has_recent_manual_activity=lead.id in recent_manual_activity_ids,
            task_completed_recently=lead.id in recent_task_completed_ids,
            now=now,
        )
        win_probability_by_lead_id[lead.id] = win_probability
        expected_value_by_lead_id[lead.id] = round(
            get_lead_estimated_value(lead) * win_probability / 100
        )
    highest_expected_value = max(expected_value_by_lead_id.values(), default=0)

    responses = []
    for lead in leads:
        is_overdue = lead.next_action_due_at is not None and lead.next_action_due_at < now
        days_overdue = (now - lead.next_action_due_at).days if is_overdue else None
        days_idle = (now - lead.updated_at).days

        win_probability = win_probability_by_lead_id[lead.id]
        expected_value = expected_value_by_lead_id[lead.id]
        # estimated_value (raw, unweighted) is still needed on its own
        # below — same cheap, pure function the precompute pass above
        # already called once per lead.
        estimated_value = get_lead_estimated_value(lead)

        latest_response = latest_response_by_lead.get(lead.id)
        lead_response_state = (
            RESPONSE_STATE_BY_EVENT_TYPE.get(latest_response.event_type, "no_response")
            if latest_response is not None
            else "no_response"
        )
        response_time_minutes = (
            round(latest_response.duration_seconds / 60)
            if latest_response is not None and latest_response.duration_seconds is not None
            else None
        )

        latest_message_sent = latest_message_sent_by_lead.get(lead.id)
        response_delay_minutes = (
            round((now - latest_message_sent.created_at).total_seconds() / 60)
            if latest_message_sent is not None
            else None
        )
        has_pending_response = latest_message_sent is not None and (
            latest_response is None or latest_response.created_at < latest_message_sent.created_at
        )

        last_activity_at = last_activity_by_lead.get(lead.id)
        days_since_last_activity = (
            (now - last_activity_at).days if last_activity_at is not None else days_idle
        )

        # Autonomous-sales-OS round — intelligent pipeline pruning. Computed
        # once, up front, since it drives three separate downstream things
        # below: compute_lead_score()'s own penalty, an override of
        # deal_risk_level/action_type after they're computed, and
        # build_priority_reason()'s extra clause. Never true for a
        # converted lead (win_probability is forced to 100) or, in
        # practice, a lost one (expected_value is always 0 there, but
        # deal_risk_level/action_type are already "low"/"drop_lead" for
        # lost leads regardless, so the override below is a no-op either
        # way).
        is_low_potential = (
            win_probability < _PRUNE_WIN_PROBABILITY_THRESHOLD
            and expected_value < _PRUNE_EXPECTED_VALUE_THRESHOLD
            and days_since_last_activity > _PRUNE_IDLE_DAYS_THRESHOLD
        ) or (
            # Auto Drop Inteligente refinement (Elite round, Task 9) — a
            # second, value-agnostic trigger: this unlikely to close and
            # this neglected is dead regardless of expected_value, catching
            # a big-looking lead the value-gated rule above would otherwise
            # keep protecting.
            win_probability < _PRUNE_HARD_WIN_PROBABILITY_THRESHOLD
            and days_since_last_activity > _PRUNE_HARD_IDLE_DAYS_THRESHOLD
        )

        # Opportunity Cost Engine (Task 1, revenue-maximization round) —
        # how much more this org's single highest-value lead is worth than
        # this one. is_high_opportunity_cost also requires this lead to be
        # the one actually getting attention right now — has_recent_manual_
        # activity is the closest available proxy for "being interacted
        # with" (no "selected in the UI" signal reaches this backend at
        # all), so it stands in for that half of the prompt's own
        # condition.
        opportunity_cost = highest_expected_value - expected_value
        is_high_opportunity_cost = (
            opportunity_cost >= _OPPORTUNITY_COST_THRESHOLD
            and lead.id in recent_manual_activity_ids
        )

        # Moved ahead of compute_lead_score()/compute_next_best_action()
        # (execution-engine round): both now need deal_risk_level (the
        # force-priority rule) and/or action_type (the action-learning
        # bonus), which used to only be computed after them.
        deal_risk_level, deal_risk_reason = compute_deal_risk(
            lead,
            expected_value=expected_value,
            win_probability=win_probability,
            is_overdue=is_overdue,
            now=now,
        )
        action_type, action_urgency = compute_action_type_and_urgency(
            lead,
            deal_risk_level,
            expected_value=expected_value,
            top_revenue_action=top_revenue_action,
            acceleration_mode=acceleration_mode,
            win_probability=win_probability,
            hunter_mode=hunter_mode,
        )
        if is_low_potential:
            deal_risk_level = "low"
            deal_risk_reason = "Lead sem potencial de receita — recomendado descarte."
            action_type = "drop_lead"
            action_urgency = "low"

        score, breakdown = compute_lead_score(
            lead,
            has_recent_automation=lead.id in recent_lead_ids,
            has_recent_manual_activity=lead.id in recent_manual_activity_ids,
            task_completed_recently=lead.id in recent_task_completed_ids,
            insights=insights,
            lead_response_state=lead_response_state,
            best_response_industry=response_metrics.best_response_industry,
            is_overdue=is_overdue,
            win_probability=win_probability,
            expected_value=expected_value,
            has_pending_response=has_pending_response,
            response_delay_minutes=response_delay_minutes,
            response_time_minutes=response_time_minutes,
            days_since_last_activity=days_since_last_activity,
            action_type=action_type,
            call_success_rate=action_effectiveness.call_success_rate,
            message_success_rate=action_effectiveness.message_success_rate,
            top_revenue_action=top_revenue_action,
            is_low_potential=is_low_potential,
            opportunity_cost=opportunity_cost,
            is_high_opportunity_cost=is_high_opportunity_cost,
            acceleration_mode=acceleration_mode,
            top_combination=top_combination,
            deal_risk_level=deal_risk_level,
            hunter_mode=hunter_mode,
            adaptive_weights=adaptive_weights,
            now=now,
        )

        # Deal Momentum Score (Elite round, Task 4) — 0-100 "how hot is
        # this deal right now," distinct from score itself; see
        # compute_momentum()'s own docstring.
        momentum_score = compute_momentum(
            lead,
            has_recent_manual_activity=lead.id in recent_manual_activity_ids,
            lead_response_state=lead_response_state,
            task_completed_recently=lead.id in recent_task_completed_ids,
            days_since_last_activity=days_since_last_activity,
        )

        # Individual close-date forecast (Elite round, Task 8).
        close_date_prediction = compute_close_date_prediction(
            lead,
            avg_time_to_close_days=insights.avg_time_to_close_days,
            win_probability=win_probability,
        )

        next_best_action = compute_next_best_action(
            lead,
            is_overdue=is_overdue,
            now=now,
            win_probability=win_probability,
            has_pending_response=has_pending_response,
            response_delay_minutes=response_delay_minutes,
            deal_risk_level=deal_risk_level,
        )
        # Smart Message Generator (Elite round, Task 2) — same template
        # content generate_lead_message_by_action() already builds, wrapped
        # with a tone (urgent/consultive/direct) driven by deal_risk_level
        # plus context from response_state/top_combination; see
        # generate_smart_message()'s own docstring.
        suggested_message = (
            generate_smart_message(
                lead,
                next_best_action,
                lead.owner_email or "the team",
                deal_risk_level=deal_risk_level,
                lead_response_state=lead_response_state,
                matches_top_combination=_matches_top_combination(lead, action_type, top_combination),
            )
            if next_best_action is not None and settings.AI_ENABLED
            else None
        )

        priority_reason = build_priority_reason(
            lead,
            estimated_value=round(estimated_value),
            win_probability=win_probability,
            days_idle=days_idle,
            is_overdue=is_overdue,
            is_low_potential=is_low_potential,
            is_high_opportunity_cost=is_high_opportunity_cost,
        )

        # Execution-assistance round — "ready to just do it" gate. Not its
        # own compute_*() function: it's a plain two-field AND already fully
        # expressed by values this loop iteration already has in scope, so a
        # separate function would just be indirection.
        is_ready_to_send = action_type == "send_message" and suggested_message is not None
        ready_to_send_message = suggested_message if is_ready_to_send else None

        response = LeadResponse.model_validate(lead)
        responses.append(
            response.model_copy(
                update={
                    "score": score,
                    "score_breakdown": breakdown,
                    "is_overdue": is_overdue,
                    "days_overdue": days_overdue,
                    "next_best_action": next_best_action,
                    "suggested_message": suggested_message,
                    "win_probability": win_probability,
                    "estimated_value": round(estimated_value),
                    "expected_value": expected_value,
                    "priority_reason": priority_reason,
                    "deal_risk_level": deal_risk_level,
                    "deal_risk_reason": deal_risk_reason,
                    "next_best_action_type": action_type,
                    "next_best_action_urgency": action_urgency,
                    "ready_to_send_message": ready_to_send_message,
                    "auto_action_available": is_ready_to_send,
                    "lead_response_state": lead_response_state,
                    "response_time_minutes": response_time_minutes,
                    "has_pending_response": has_pending_response,
                    "response_delay_minutes": response_delay_minutes,
                    "days_since_last_activity": days_since_last_activity,
                    "opportunity_cost": opportunity_cost,
                    "acceleration_mode": acceleration_mode,
                    "momentum_score": momentum_score,
                    "lead_close_date_prediction": close_date_prediction,
                    "hunter_mode": hunter_mode,
                }
            )
        )
    return responses


# Candidate-pool size for rank_leads_by_priority() — same value and rationale
# as GET /leads/priority's own docstring: comfortably above any realistic
# per-org lead count at this product stage.
_PRIORITY_CANDIDATE_POOL_SIZE = 200


async def rank_leads_by_priority(db: AsyncSession, organization_id: str) -> list[LeadResponse]:
    """Dynamic Deal Reallocation (Task 2, revenue-maximization round)
    replaces this function's original urgency-bucket-first ordering
    (overdue tasks first, then due today, then future-dated, then no
    next_action at all — still what GET /leads/priority's own separate
    inline implementation uses, untouched by this round's mandate of zero
    regression on existing routes) with a revenue-first key: deal_risk_level
    (critical first) > expected_value DESC > win_probability DESC >
    opportunity_cost DESC > score DESC. This is a deliberate behavior
    change, not an addition — "worst-off first" is no longer this
    function's own priority, "highest revenue first" is. Callers that still
    want the original ordering (GET /leads/priority) already have their
    own separate implementation, unaffected; get_next_actionable_lead()
    (workday_engine.py, POST /workday/complete-and-next) now hands back
    whichever lead maximizes revenue rather than whichever is most overdue.

    Money-first override on top: any lead worth >=
    _REALLOCATION_FORCE_TOP_VALUE with win_probability >=
    _REALLOCATION_FORCE_TOP_WIN_PROBABILITY is pulled into the very top
    _REALLOCATION_FORCE_TOP_SLOTS positions regardless of risk tier — same
    technique build_action_queue()'s own money-first override
    (workday_engine.py) already uses."""
    candidate_pool_stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.status != "converted",
        )
        .order_by(Lead.next_action_due_at.asc().nulls_last())
        .limit(_PRIORITY_CANDIDATE_POOL_SIZE)
    )
    candidates = (await db.execute(candidate_pool_stmt)).scalars().all()

    scored = await score_leads(db, candidates)

    scored.sort(
        key=lambda response: (
            -_RISK_LEVEL_ORDER.get(response.deal_risk_level, 0),
            -response.expected_value,
            -response.win_probability,
            -response.opportunity_cost,
            -response.score,
            # Deal Momentum Score (Elite round, Task 4) — the prompt's own
            # final tiebreaker: among otherwise-equal leads, whichever one
            # has more recent real motion behind it goes first.
            -response.momentum_score,
        )
    )

    forced = [
        response
        for response in scored
        if response.expected_value >= _REALLOCATION_FORCE_TOP_VALUE
        and response.win_probability >= _REALLOCATION_FORCE_TOP_WIN_PROBABILITY
    ][:_REALLOCATION_FORCE_TOP_SLOTS]
    forced_ids = {response.id for response in forced}
    return forced + [response for response in scored if response.id not in forced_ids]


def compute_forecast_value(response: LeadResponse) -> float:
    """GET /revenue/forecast's own per-lead figure (Revenue Forecast
    Engine, Autonomous-sales-OS round) — response.expected_value (already
    win_probability-weighted by score_leads()) further discounted by how
    stale this lead looks, since a stalling deal's plain expected_value
    overstates how much of that money will actually land within the
    forecast period. Overdue is checked before idle (a harsher signal —
    same "worse condition wins," not "conditions stack," precedent
    compute_deal_risk's own severity ordering already sets): idle uses
    days_since_last_activity (LeadActivityLog-derived — see that field's
    own docstring for why it's the sharper "idle" signal, distinct from
    the updated_at-derived days_idle several compute_lead_score() lines
    use instead) rather than updated_at, since this is itself a read-time
    aggregate over an already-scored LeadResponse, not a fresh Lead row."""
    if response.is_overdue:
        return response.expected_value * _FORECAST_OVERDUE_DECAY
    if response.days_since_last_activity > _FORECAST_IDLE_DECAY_DAYS:
        return response.expected_value * _FORECAST_IDLE_DECAY
    return response.expected_value * 1.0


# Revenue Simulation Engine's own optimistic boost (Task 5, Adaptive
# Intelligence round) — the prompt's own +10-20% win_probability range: the
# larger boost for a lead with a real pending action still outstanding
# (ready_to_send_message populated, or a message sent with no reply yet —
# "executing all pending actions" most directly helps exactly these), the
# smaller one for every other still-open lead (the "reduced response
# delay" half of the prompt's own assumption still applies generally).
_SIMULATION_PENDING_ACTION_BOOST = 20
_SIMULATION_BASELINE_BOOST = 10


def simulate_revenue_if_all_actions_executed(leads: list[LeadResponse]) -> dict:
    """Revenue Simulation Engine (Task 5, Adaptive Intelligence round) — a
    deterministic "best case" projection, not a forecast: current_expected
    sums every still-open lead's own already-computed expected_value
    (score_leads()'s own win_probability-weighted figure); optimized_expected
    re-weights each one's win_probability upward by _SIMULATION_PENDING_
    ACTION_BOOST/_SIMULATION_BASELINE_BOOST (see those constants' own
    comment), capped at 100, and re-derives expected_value from that boosted
    probability against the lead's own unweighted estimated_value. No ML,
    no randomness — same fixed-multiplier "what if" style as
    compute_forecast_value() just above, just optimistic instead of
    pessimistic. Pure, no DB access — operates on an already-scored
    `leads` list exactly like that function does."""
    current_expected = 0
    optimized_expected = 0
    for response in leads:
        if response.status in ("converted", "lost"):
            continue
        current_expected += response.expected_value

        has_pending_action = response.has_pending_response or response.ready_to_send_message is not None
        boost = _SIMULATION_PENDING_ACTION_BOOST if has_pending_action else _SIMULATION_BASELINE_BOOST
        optimized_win_probability = min(100, response.win_probability + boost)
        optimized_expected += round(response.estimated_value * optimized_win_probability / 100)

    return {
        "current_expected": current_expected,
        "optimized_expected": optimized_expected,
        "delta": optimized_expected - current_expected,
    }


# Global Strategy Engine's own thresholds (Task 2, final round) — the
# prompt's own literal signals, each checked highest-priority first: a
# structural communication problem (rule 1) outranks even a hot pipeline
# (rule 2), which in turn outranks a merely-learned channel preference
# (rule 3).
_GLOBAL_STRATEGY_LOW_RESPONSE_RATE = 20.0
_GLOBAL_STRATEGY_HIGH_WIN_PROBABILITY = 70


def compute_global_strategy(
    leads: list[LeadResponse],
    *,
    response_rate: float,
    top_revenue_action: str | None,
    team_performance: list[UserPerformanceResponse] | None = None,
) -> dict:
    """Global Strategy Engine (Task 2, final round) — one recommended
    channel to focus effort on right now, plain deterministic rules (no
    ML), highest-priority rule first:
      1. response_rate below _GLOBAL_STRATEGY_LOW_RESPONSE_RATE
         (compute_response_metrics()'s own all-time figure, same one the
         Command Center's "X% das suas mensagens recebem resposta" line
         already shows) — a structural communication problem outranks any
         learned preference; focus messages until it's fixed. When
         `team_performance` is also given, the team's own average
         response_rate is folded in too (the lower of the two wins) — not
         its own separate rule, since the prompt lists exactly three
         focus signals, not four.
      2. the open pipeline's own average win_probability >=
         _GLOBAL_STRATEGY_HIGH_WIN_PROBABILITY — this close to closing is
         worth pushing toward meetings.
      3. top_revenue_action == "call" (compute_revenue_attribution()'s own
         org-wide learned highest-earning channel, reused rather than
         recomputed here) — lean into what's already proven to work.
      4. Default: messages, the safest, lowest-commitment channel when no
         signal points anywhere specific.

    Pure, no DB access — `leads`/`response_rate`/`top_revenue_action`/
    `team_performance` are all already-computed inputs a caller assembles
    from score_leads()/compute_response_metrics()/compute_revenue_
    attribution()/compute_user_performance(), the same "accept already-
    computed aggregates, don't refetch them" style
    simulate_revenue_if_all_actions_executed() just above already uses."""
    if team_performance:
        team_response_rates = [performance.response_rate for performance in team_performance]
        team_avg_response_rate = sum(team_response_rates) / len(team_response_rates)
        response_rate = min(response_rate, team_avg_response_rate)

    if response_rate < _GLOBAL_STRATEGY_LOW_RESPONSE_RATE:
        return {
            "focus": "messages",
            "reason": f"Taxa de resposta em {response_rate:.0f}% — abaixo do saudável, foque em reconectar.",
            "confidence": 80,
        }

    open_leads = [lead for lead in leads if lead.status not in ("converted", "lost")]
    avg_win_probability = (
        sum(lead.win_probability for lead in open_leads) / len(open_leads) if open_leads else 0
    )
    if avg_win_probability >= _GLOBAL_STRATEGY_HIGH_WIN_PROBABILITY:
        return {
            "focus": "meetings",
            "reason": f"Probabilidade média de fechamento em {avg_win_probability:.0f}% — hora de agendar reuniões.",
            "confidence": 85,
        }

    if top_revenue_action == "call":
        return {
            "focus": "calls",
            "reason": "Ligações são o canal que historicamente mais gera receita real.",
            "confidence": 75,
        }

    return {
        "focus": "messages",
        "reason": "Sem sinal dominante no momento — mensagens são o canal mais seguro agora.",
        "confidence": 50,
    }


# Dynamic Aggression Mode's own thresholds (Task 3, final round) — the
# prompt's own literal percentages, read against the Revenue Simulation
# Engine's own current_expected/delta (simulate_revenue_if_all_actions_
# executed(), just above) rather than a separate daily-target/gap figure
# (GET /workday/target's own WorkdayTargetResponse): that would need a
# third data source this function's own two-signal ask doesn't call for,
# where current_expected/delta already answer the same question — "how
# much upside is on the table relative to what's already expected" reads
# as exactly the "gap" the prompt's own English description points at.
_AGGRESSION_HIGH_LOST_RATIO = 0.2
_AGGRESSION_EXTREME_GAP_RATIO = 0.5


def compute_aggression_level(*, lost_opportunity_today: int, current_expected: int, delta: int) -> str:
    """Dynamic Aggression Mode (Task 3, final round) — "low"/"medium"/
    "high"/"extreme", worst-condition-first (same severity-ordering
    precedent compute_deal_risk() already sets):
      extreme — delta (the Revenue Simulation Engine's own optimistic
        upside) is more than _AGGRESSION_EXTREME_GAP_RATIO (50%) of
        current_expected: over half of what's already expected is still
        sitting there uncaptured.
      high — lost_opportunity_today (compute_lost_opportunity_today(),
        workday_engine.py) is more than _AGGRESSION_HIGH_LOST_RATIO (20%)
        of current_expected.
      low — current_expected is 0 with nothing lost today either, or
        there's no real upside left (delta <= 0) and nothing lost today —
        pipeline genuinely under control.
      medium — everything else (some real signal, but below both harsher
        bars).

    Pure, no DB access — current_expected/delta come straight from
    simulate_revenue_if_all_actions_executed()'s own return dict."""
    if current_expected <= 0:
        return "high" if lost_opportunity_today > 0 else "low"

    gap_ratio = delta / current_expected
    lost_ratio = lost_opportunity_today / current_expected

    if gap_ratio > _AGGRESSION_EXTREME_GAP_RATIO:
        return "extreme"
    if lost_ratio > _AGGRESSION_HIGH_LOST_RATIO:
        return "high"
    if delta <= 0 and lost_opportunity_today <= 0:
        return "low"
    return "medium"


# Revenue Leak Detector's own thresholds (Task 5, final round) —
# _REVENUE_LEAK_IGNORED_MINUTES reuses the same 24h bar the sales-
# operating-system round's own pending-response penalty already uses
# (_PENDING_RESPONSE_DELAY_MINUTES_HIGH), rather than a second, separately-
# tuned "ignored" threshold that could silently drift from it.
_REVENUE_LEAK_IGNORED_MINUTES = _PENDING_RESPONSE_DELAY_MINUTES_HIGH
_REVENUE_LEAK_STUCK_DAYS = 7


def detect_revenue_leaks(leads: list[LeadResponse]) -> dict:
    """Revenue Leak Detector (Task 5, final round) — three independent
    leak patterns over an already-scored `leads` list, no DB access:
      leads_ignored_over_24h — has_pending_response and
        response_delay_minutes over _REVENUE_LEAK_IGNORED_MINUTES: a
        message sent, nobody's followed up on the silence.
      high_value_leads_without_action — still-open, expected_value >=
        HIGH_VALUE_LEAD_THRESHOLD, and next_best_action_type is either
        unset or "monitor" — a big deal with no concrete next step.
      leads_stuck_same_stage — still in "new"/"contacted" (never
        progressed) and days_since_last_activity over
        _REVENUE_LEAK_STUCK_DAYS.

    total_leak_value sums expected_value across the union of all three
    (a lead counted under more than one pattern isn't double-counted)."""
    ignored = [
        lead
        for lead in leads
        if lead.has_pending_response
        and lead.response_delay_minutes is not None
        and lead.response_delay_minutes > _REVENUE_LEAK_IGNORED_MINUTES
    ]
    high_value_no_action = [
        lead
        for lead in leads
        if lead.status not in ("converted", "lost")
        and lead.expected_value >= HIGH_VALUE_LEAD_THRESHOLD
        and lead.next_best_action_type in (None, "monitor")
    ]
    stuck = [
        lead
        for lead in leads
        if lead.status in ("new", "contacted")
        and lead.days_since_last_activity > _REVENUE_LEAK_STUCK_DAYS
    ]

    leaking_lead_ids = (
        {lead.id for lead in ignored}
        | {lead.id for lead in high_value_no_action}
        | {lead.id for lead in stuck}
    )
    total_leak_value = sum(
        lead.expected_value for lead in leads if lead.id in leaking_lead_ids
    )

    return {
        "leads_ignored_over_24h": len(ignored),
        "high_value_leads_without_action": len(high_value_no_action),
        "leads_stuck_same_stage": len(stuck),
        "total_leak_value": total_leak_value,
    }


# Auto-Correction Engine's own thresholds (Task 6, final round).
_AUTO_CORRECT_NEGLECT_DAYS = 3
_AUTO_CORRECT_COLD_WIN_PROBABILITY = 15


def auto_correct_pipeline(leads: list[LeadResponse]) -> list[LeadResponse]:
    """Auto-Correction Engine (Task 6, final round) — a pure, in-memory
    second pass over an already-scored/ranked `leads` list: no DB write,
    no mutation of anything persisted, just a corrected copy of the list
    a caller can render instead of the raw one.
      escalate neglected leads — still open, idle over
        _AUTO_CORRECT_NEGLECT_DAYS days, and not cold (see below):
        next_best_action_urgency bumped to "high" (never above
        "immediate" — an escalation, not a false emergency).
      downgrade cold leads — win_probability under
        _AUTO_CORRECT_COLD_WIN_PROBABILITY AND idle over
        _AUTO_CORRECT_NEGLECT_DAYS: urgency dropped to "low". Checked
        *before* the escalation rule above (a lead matching both reads as
        "genuinely dead," not "neglected but still worth chasing" — same
        "worse condition wins, conditions don't stack" precedent
        compute_deal_risk()'s own severity ordering already sets).
      re-prioritize queue — the corrected list is re-sorted by the exact
        same revenue-first key rank_leads_by_priority() already uses
        (risk tier, expected_value, win_probability, opportunity_cost,
        score, momentum_score), so a caller sees a freshly-corrected
        order without a second DB round-trip.

    Idempotent: running this twice on its own output is a no-op the
    second time (nothing left to escalate/downgrade differently) other
    than the sort itself, which is already stable at that point too."""
    corrected: list[LeadResponse] = []
    for lead in leads:
        urgency = lead.next_best_action_urgency
        if lead.status not in ("converted", "lost"):
            is_cold = (
                lead.win_probability < _AUTO_CORRECT_COLD_WIN_PROBABILITY
                and lead.days_since_last_activity > _AUTO_CORRECT_NEGLECT_DAYS
            )
            if is_cold:
                urgency = "low"
            elif lead.days_since_last_activity > _AUTO_CORRECT_NEGLECT_DAYS and urgency != "immediate":
                urgency = "high"

        corrected.append(
            lead if urgency == lead.next_best_action_urgency
            else lead.model_copy(update={"next_best_action_urgency": urgency})
        )

    corrected.sort(
        key=lambda response: (
            -_RISK_LEVEL_ORDER.get(response.deal_risk_level, 0),
            -response.expected_value,
            -response.win_probability,
            -response.opportunity_cost,
            -response.score,
            -response.momentum_score,
        )
    )
    return corrected
