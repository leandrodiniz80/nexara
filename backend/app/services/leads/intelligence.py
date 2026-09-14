from __future__ import annotations

import math

from app.schemas.leads.lead import LeadResponse
from app.schemas.performance import UserPerformanceResponse
from app.services.leads.enrichment import HIGH_VALUE_LEAD_THRESHOLD, format_brl
from app.services.leads.scoring import ACTION_EVENT_TYPE_TO_ACTION_TYPE

# ADVANCED LAYER — this module's original per-signal endpoints
# (/intelligence/adaptive-weights, /trends, /global-strategy,
# /aggression-level, /revenue-leaks, etc., routers/intelligence.py) stay
# exactly as they are: a visibility/debugging layer over individual
# engines. compute_global_decision()/compute_product_summary() below are
# the product-consolidation round's own PRIMARY layer — see their own
# docstrings and routers/product.py.

# generate_exec_insight()'s own next_action → PT action phrase (product-
# consolidation round) — the same vocabulary compute_action_type_and_urgency()
# (scoring.py) and GET /workday/enforcement-state's own required_action
# already use (call_now/send_message/schedule_meeting), plus "monitor" for
# when compute_global_decision() finds nothing mandatory.
_NEXT_ACTION_LABEL_PT = {
    "call_now": "ligar para os leads críticos agora",
    "send_message": "enviar mensagens aos leads pendentes agora",
    "schedule_meeting": "agendar reuniões com os leads quentes agora",
    "monitor": "monitorar o pipeline — nenhuma ação crítica pendente",
}


def compute_global_decision(
    *,
    mandatory_lead: LeadResponse | None,
    required_action: str | None,
    reason: str | None,
    aggression_level: str,
) -> dict:
    """Global Decision Engine (Task 1, product-consolidation round) — the
    single "what should happen right now" decision for the whole system.
    Deliberately NOT a new computation: mandatory_lead/required_action/
    reason are GET /workday/enforcement-state's own pipeline
    (build_action_queue()+get_next_mandatory_lead(), workday_engine.py),
    passed in verbatim by the caller rather than recomputed here — the same
    inputs that endpoint itself already derives from one
    rank_leads_by_priority() pool. aggression_level is
    compute_aggression_level()'s own output (scoring.py), reused for the
    same reason.

    This is what Task 5's "guaranteed consistency" actually means in
    practice: GET /product/summary, GET /intelligence/exec-insight, and GET
    /workday/enforcement-state all read next_action/execution_blocked from
    THIS single dict (or from the exact same mandatory_lead/required_action
    inputs that produced it) instead of each independently deciding what
    "the" next action is — so they cannot drift apart.

    next_action falls back to "monitor" and execution_blocked to False only
    when there's no mandatory_lead at all — pipeline genuinely under
    control, nothing forces one specific action right now."""
    if mandatory_lead is None:
        return {
            "next_action": "monitor",
            "execution_blocked": False,
            "reason": "Pipeline sob controle — nenhuma ação crítica pendente.",
            "aggression_level": aggression_level,
        }

    return {
        "next_action": required_action,
        "execution_blocked": True,
        "reason": reason,
        "aggression_level": aggression_level,
    }


def compute_product_summary(
    ranked: list[LeadResponse],
    *,
    revenue_today_expected: int,
    revenue_today_gap: float,
    revenue_at_risk: int,
    decision: dict,
) -> dict:
    """Product Summary / CEO View (Task 2, product-consolidation round) —
    the system's single "explain it in seconds" snapshot. Pure aggregation
    of figures every other endpoint already computes — no new calculation
    anywhere in here:
      revenue_today_expected — sum_today_potential_revenue() (workday_
        engine.py), the exact figure GET /workday/summary already calls
        today_potential_revenue and GET /workday/target already calls
        current_expected.
      revenue_today_gap — GET /workday/target's own daily_target_revenue
        minus that same today-expected figure (passed in by the caller,
        product.py, using compute_daily_target_revenue() — workday_
        engine.py).
      revenue_at_risk — compute_revenue_at_risk() (workday_engine.py), the
        exact figure GET /workday/summary already exposes under the same
        name.
      biggest_opportunity — the single highest expected_value lead still
        open in `ranked`, the same rank_leads_by_priority() pool every
        other figure here is drawn from.
      next_action/execution_blocked — read straight off
        compute_global_decision()'s own `decision` dict, never re-derived
        here, so this can never disagree with GET /workday/enforcement-
        state or GET /intelligence/exec-insight (Task 5)."""
    open_leads = [lead for lead in ranked if lead.status not in ("converted", "lost")]
    biggest = max(open_leads, key=lambda lead: lead.expected_value, default=None)
    biggest_opportunity = (
        {
            "lead_id": biggest.id,
            "name": biggest.name,
            "company_name": biggest.company_name,
            "expected_value": biggest.expected_value,
        }
        if biggest is not None
        else None
    )

    return {
        "revenue_today_expected": revenue_today_expected,
        "revenue_today_gap": revenue_today_gap,
        "revenue_at_risk": revenue_at_risk,
        "biggest_opportunity": biggest_opportunity,
        "next_action": decision["next_action"],
        "execution_blocked": decision["execution_blocked"],
    }


def generate_exec_insight(*, revenue_today_expected: int, lost_opportunity_today: int, next_action: str) -> str:
    """CEO Insight Layer, final form (Task 4, product-consolidation round)
    — exactly one sentence, same fixed template every time:
    "Hoje você pode gerar R$X, mas está deixando R$Y na mesa. A ação agora
    é: Z." X is revenue_today_expected (sum_today_potential_revenue(),
    workday_engine.py — that function's own docstring literally is "Hoje
    você pode gerar R$ X"). Y is lost_opportunity_today
    (compute_lost_opportunity_today(), workday_engine.py — "money left on
    the table right now," this codebase's own established framing for that
    exact figure, see generate_accountability_message()'s "dinheiro na
    mesa" phrasing). Z is compute_global_decision()'s own next_action,
    translated to a short PT action phrase — the SAME value GET
    /product/summary and GET /workday/enforcement-state read (Task 5
    consistency).

    Replaces the prior multi-signal narrative version (a separate sentence
    each for aggression level, strategy focus, and leak count) per this
    round's own explicit "Refactor... Return EXACTLY" instruction. The
    ExecInsightResponse API contract ({message: str}) is unchanged — only
    the string's content."""
    action_label = _NEXT_ACTION_LABEL_PT.get(next_action, next_action)
    return (
        f"Hoje você pode gerar R$ {format_brl(revenue_today_expected)}, "
        f"mas está deixando R$ {format_brl(lost_opportunity_today)} na mesa. "
        f"A ação agora é: {action_label}."
    )


# ---------------------------------------------------------------------------
# PRODUCT LAYER (product-layer round) — universal, industry-agnostic
# abstractions on top of everything above. Every function below is pure
# aggregation over already-computed signals (the `signals` dict product.py
# assembles from rank_leads_by_priority()/simulate_revenue_if_all_actions_
# executed()/compute_response_metrics()/detect_revenue_leaks()/
# compute_global_decision() — no new query, no re-scoring, no per-industry
# special-casing anywhere here: everything is driven by numbers already on
# the lead/summary, which is what keeps this layer valid for any vertical,
# not just the one a given tenant happens to sell into.
# ---------------------------------------------------------------------------

# compute_product_mode()'s own thresholds (Task 1, product-layer round) —
# the round's own literal numbers. Deliberately currency-unit-agnostic (no
# per-country/per-industry scaling): estimated_value is already whatever
# unit this tenant's own leads are enriched in.
_VOLUME_AVG_DEAL_VALUE_MAX = 2000
_PRECISION_AVG_DEAL_VALUE_MIN = 10000


def compute_product_mode(
    leads: list[LeadResponse],
    summary: dict | None = None,
    performance: list[UserPerformanceResponse] | None = None,
) -> str:
    """Product Mode (Task 1, product-layer round) — the one abstraction
    everything else in this section keys off of: "volume" (many leads, low
    ticket, speed matters), "precision" (few leads, high ticket, quality
    matters), or "hybrid" (both). Classified purely from avg_deal_value —
    the mean estimated_value (score_leads()'s own unweighted deal size,
    scoring.py) across whatever `leads` the caller already scored — against
    this round's own two thresholds. No status/industry/segment special-
    casing: any vertical with small, frequent deals reads as "volume" and
    any vertical with rare, large ones reads as "precision," by construction.

    `summary`/`performance` are accepted for signature parity with this
    round's own spec and reserved for future signal-blending (e.g. a team
    that's mostly one rep might want a different default) — the rule this
    round actually specifies only needs avg_deal_value, so neither is read
    yet. Defaults to "hybrid" with an empty pool — no deals means no signal
    either way."""
    if not leads:
        return "hybrid"

    avg_deal_value = sum(lead.estimated_value for lead in leads) / len(leads)
    if avg_deal_value < _VOLUME_AVG_DEAL_VALUE_MAX:
        return "volume"
    if avg_deal_value > _PRECISION_AVG_DEAL_VALUE_MIN:
        return "precision"
    return "hybrid"


# compute_dynamic_kpis()'s own per-mode profile (Task 2, product-layer
# round) — the round's own literal numbers/labels for each mode. Kept as
# one lookup table (not three near-identical if/elif branches) so adding a
# future mode is one new entry, not a new branch scattered across the
# function body.
_KPI_PROFILE_BY_PRODUCT_MODE = {
    "volume": {
        "ideal_response_time_minutes": 5,
        "ideal_actions_per_day": 50,
        "focus_metric": "speed",
    },
    "precision": {
        "ideal_response_time_minutes": 30,
        "ideal_actions_per_day": 15,
        "focus_metric": "conversion_quality",
    },
    "hybrid": {
        "ideal_response_time_minutes": 15,
        "ideal_actions_per_day": 30,
        "focus_metric": "balance",
    },
}


def compute_dynamic_kpis(product_mode: str, summary: dict) -> dict:
    """Automatic KPI Adaptation (Task 2, product-layer round) — response-
    time/actions-per-day/focus_metric targets read straight off
    _KPI_PROFILE_BY_PRODUCT_MODE for whatever compute_product_mode() just
    decided (falls back to "hybrid"'s own balanced profile for an unknown
    mode, never raises). daily_target_revenue is not a new figure: it's
    `summary`'s own daily_target_revenue — the exact same value
    compute_daily_target_revenue() (workday_engine.py) and GET
    /workday/target already compute, threaded through by the caller
    (product.py) rather than recomputed here."""
    profile = _KPI_PROFILE_BY_PRODUCT_MODE.get(product_mode, _KPI_PROFILE_BY_PRODUCT_MODE["hybrid"])

    return {
        "daily_target_revenue": summary.get("daily_target_revenue", 0),
        "ideal_response_time_minutes": profile["ideal_response_time_minutes"],
        "ideal_actions_per_day": profile["ideal_actions_per_day"],
        "focus_metric": profile["focus_metric"],
    }


# compute_sales_readiness()'s own weights (Task 3, product-layer round) —
# the round's own literal point values. Each ratio is clamped to [0, 1]
# before being scaled, so no single signal can push the score outside its
# own allotted band (e.g. a response_rate that reads >100% per compute_
# response_metrics()'s own disclosed approximation still only ever
# contributes its full +30, never more).
_READINESS_PIPELINE_WEIGHT = 40
_READINESS_RESPONSE_WEIGHT = 30
_READINESS_EXECUTION_WEIGHT = 20
_READINESS_LEAK_PENALTY = 30
_READINESS_OVERDUE_PENALTY = 20


def compute_sales_readiness(
    summary: dict, performance: list[UserPerformanceResponse] | None, leaks: dict
) -> int:
    """Sales Readiness Score (Task 3, product-layer round) — 0-100, the
    SaaS metric a customer checks first. Every input is already computed
    elsewhere, this only blends them:
      pipeline vs target (+40) — summary's own current_expected (simulate_
        revenue_if_all_actions_executed(), scoring.py) against
        daily_target_revenue (compute_daily_target_revenue(),
        workday_engine.py); no target yet reads as fully ready (1.0), not
        a penalty.
      response rate (+30) — summary's own response_rate (compute_response_
        metrics(), scoring.py).
      execution rate (+20) — summary's own execution_rate: current_
        expected / optimized_expected (simulate_revenue_if_all_actions_
        executed()'s own two figures) — how much of the achievable upside
        is already being captured, not a new effectiveness metric.
      revenue leaks (-30) — leaks's own total_leak_value (detect_revenue_
        leaks(), scoring.py) as a share of current_expected.
      overdue leads (-20) — summary's own overdue_count over
        total_open_leads (both already counted off the same `ranked` pool
        every other figure here is drawn from).

    `performance` is accepted for signature parity with this round's own
    spec — none of the five components above need per-user detail, so it
    isn't read yet; team-level performance is already exposed separately
    (GET /performance/team-summary) rather than duplicated into this
    formula. Clamped to [0, 100]."""
    daily_target_revenue = summary.get("daily_target_revenue", 0)
    current_expected = summary.get("current_expected", 0)
    pipeline_ratio = (
        min(current_expected / daily_target_revenue, 1.0) if daily_target_revenue > 0 else 1.0
    )

    response_ratio = min(summary.get("response_rate", 0.0) / 100, 1.0)
    execution_ratio = min(summary.get("execution_rate", 0.0) / 100, 1.0)

    total_leak_value = leaks.get("total_leak_value", 0)
    leak_ratio = min(total_leak_value / current_expected, 1.0) if current_expected > 0 else 0.0

    total_open_leads = summary.get("total_open_leads", 0)
    overdue_ratio = (
        min(summary.get("overdue_count", 0) / total_open_leads, 1.0) if total_open_leads > 0 else 0.0
    )

    score = (
        _READINESS_PIPELINE_WEIGHT * pipeline_ratio
        + _READINESS_RESPONSE_WEIGHT * response_ratio
        + _READINESS_EXECUTION_WEIGHT * execution_ratio
        - _READINESS_LEAK_PENALTY * leak_ratio
        - _READINESS_OVERDUE_PENALTY * overdue_ratio
    )
    return round(max(0, min(100, score)))


# ---------------------------------------------------------------------------
# REVENUE COMMAND CENTER (revenue-command-center round) — this round adds
# no new intelligence: every function below still only aggregates figures
# the product layer above (or scoring.py/workday_engine.py underneath it)
# already computed. The goal is pressure and forced action, not new
# analysis — no per-industry logic anywhere, same universal, currency-
# unit-agnostic stance as the product layer.
# ---------------------------------------------------------------------------


def compute_revenue_gap(summary: dict, target: dict) -> float:
    """Revenue Gap (Task 1, revenue-command-center round) — the pressure-
    facing, floored-at-zero sibling of revenue_today_gap
    (compute_product_summary(), above): revenue_today_gap can read
    negative when this tenant is already ahead of daily_target_revenue (a
    surplus, not a shortfall), which is fine for an informational field but
    wrong for a number this round's pressure_message/required_actions
    display as money being lost — 0 there means "no shortfall," never "no
    data." target.daily_target_revenue is compute_dynamic_kpis()'s own
    figure (itself compute_daily_target_revenue(), workday_engine.py,
    reused not recomputed); summary.revenue_today_possible is sum_today_
    potential_revenue()'s same figure under this round's own literal name
    (compute_product_summary()'s revenue_today_expected)."""
    daily_target_revenue = target.get("daily_target_revenue", 0)
    revenue_today_possible = summary.get("revenue_today_possible", 0)
    return max(daily_target_revenue - revenue_today_possible, 0)


# compute_main_action()'s own thresholds/vocabulary (Task 2, revenue-
# command-center round — REPLACES the prior generic version below).
# HIGH_VALUE_LEAD_THRESHOLD (enrichment.py) is the same bar detect_
# revenue_leaks() already uses; _HIGH_WIN_PROBABILITY_THRESHOLD mirrors
# scoring.py's own private constant of the same name/value (70) — kept as
# its own local copy rather than a cross-module import of a name used 11
# times inside scoring.py's own internals, same "independent constant, same
# value, disclosed" precedent GET /workday/target's own
# _ACCELERATION_MODE_GAP_THRESHOLD already sets against scoring.py's
# compute_acceleration_mode(). days_since_last_activity >= 1 is compute_
# lost_opportunity_today()'s own idle bar (workday_engine.py).
_HIGH_WIN_PROBABILITY_THRESHOLD = 70
_MAIN_ACTION_IDLE_DAYS = 1

_MAIN_ACTION_VERB_BY_TYPE = {
    "call_now": "Ligue agora para",
    "send_message": "Envie mensagem para",
    "schedule_meeting": "Priorize reuniões com",
}


def _dominant_action_type(leads: list[LeadResponse]) -> str:
    """The most common next_best_action_type (compute_action_type_and_
    urgency()'s own vocabulary, scoring.py) among `leads` — picks
    compute_main_action()'s verb without inventing a new classification."""
    counts: dict[str, int] = {}
    for lead in leads:
        action_type = lead.next_best_action_type or "send_message"
        counts[action_type] = counts.get(action_type, 0) + 1
    return max(counts, key=counts.get)


def compute_main_action(leads: list[LeadResponse]) -> str:
    """Hard Main Action (Task 2, revenue-command-center round) — REPLACES
    the prior generic version. Always specific, numeric, direct: a real
    count of real leads clearing real thresholds, never a vague nudge.
    Priority, worst-and-most-valuable-first:
      1. open leads that are idle-or-overdue AND high-value (expected_
         value >= HIGH_VALUE_LEAD_THRESHOLD) AND high-win-probability
         (win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD) — the exact
         "highest expected_value, highest win_probability, idle or
         overdue" combination this round asks for, sorted by
         (expected_value, win_probability) desc. The dominant
         next_best_action_type among them (majority vote,
         _dominant_action_type() above) picks the verb.
      2. any overdue open lead, regardless of value — "leads atrasados."
      3. any idle (not overdue) open lead — "leads parados há mais de
         24h."
      4. otherwise — pipeline genuinely under control, no candidate
         clears even the idle bar."""
    open_leads = [lead for lead in leads if lead.status not in ("converted", "lost")]
    idle_or_overdue = [
        lead
        for lead in open_leads
        if lead.is_overdue or lead.days_since_last_activity >= _MAIN_ACTION_IDLE_DAYS
    ]
    if not idle_or_overdue:
        return "Continue executando o plano atual — pipeline sob controle."

    hot = [
        lead
        for lead in idle_or_overdue
        if lead.expected_value >= HIGH_VALUE_LEAD_THRESHOLD
        and lead.win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD
    ]
    if hot:
        hot.sort(key=lambda lead: (lead.expected_value, lead.win_probability), reverse=True)
        verb = _MAIN_ACTION_VERB_BY_TYPE.get(_dominant_action_type(hot), "Priorize")
        return (
            f"{verb} {len(hot)} leads acima de R$ {format_brl(HIGH_VALUE_LEAD_THRESHOLD)} "
            "com alta chance de fechamento."
        )

    overdue = [lead for lead in idle_or_overdue if lead.is_overdue]
    if overdue:
        verb = _MAIN_ACTION_VERB_BY_TYPE.get(_dominant_action_type(overdue), "Priorize")
        return f"{verb} {len(overdue)} leads atrasados agora."

    verb = _MAIN_ACTION_VERB_BY_TYPE.get(_dominant_action_type(idle_or_overdue), "Priorize")
    return f"{verb} {len(idle_or_overdue)} leads parados há mais de 24h."


# compute_required_actions()'s own bias ratio (Task 3, revenue-command-
# center round) — the biased channel's own share of required_actions_today
# when there's a clear next_action signal; the other channel takes the
# remainder. Even 50/50 split otherwise. FOCUS_BY_NEXT_ACTION reuses
# compute_global_decision()'s own next_action (this module) rather than a
# separate Global Strategy Engine call (compute_global_strategy(), which
# needs two more queries GET /product/summary doesn't otherwise pay for) —
# same "calls"/"messages"/"meetings" vocabulary that engine's own `focus`
# field already uses, just derived from a signal already in hand.
_REQUIRED_ACTIONS_BIAS_RATIO = 0.7
FOCUS_BY_NEXT_ACTION = {
    "call_now": "calls",
    "send_message": "messages",
    "schedule_meeting": "meetings",
}


def compute_required_actions(summary: dict, target: dict, kpis: dict) -> dict:
    """Forced KPI (Task 3, revenue-command-center round) — turns
    revenue_gap into a concrete daily action quota, an obligation rather
    than a suggestion. avg_expected_value_per_action is not a new figure:
    summary's own current_expected (simulate_revenue_if_all_actions_
    executed(), scoring.py) divided by total_open_leads (both already
    counted off the same `ranked` pool every other figure here reads) —
    the average expected value one open lead/action represents right now.
    required_actions_today = ceil(target.revenue_gap /
    avg_expected_value_per_action), floored at kpis.ideal_actions_per_day
    (compute_dynamic_kpis(), above) — this tenant's own product_mode
    baseline is never undercut by a small gap. 0/0/0 when there's no gap
    or no open pipeline to act on at all.

    Split by summary's own next_action via FOCUS_BY_NEXT_ACTION above:
    call_now biases required_calls_today, send_message biases required_
    messages_today (each at _REQUIRED_ACTIONS_BIAS_RATIO of the total),
    anything else splits evenly."""
    revenue_gap = target.get("revenue_gap", 0)
    current_expected = summary.get("current_expected", 0)
    total_open_leads = summary.get("total_open_leads", 0)
    avg_expected_value_per_action = (
        current_expected / total_open_leads if total_open_leads > 0 else 0
    )

    if revenue_gap <= 0 or avg_expected_value_per_action <= 0:
        return {
            "required_actions_today": 0,
            "required_calls_today": 0,
            "required_messages_today": 0,
        }

    required_actions_today = math.ceil(revenue_gap / avg_expected_value_per_action)
    required_actions_today = max(required_actions_today, kpis.get("ideal_actions_per_day", 0))

    focus = FOCUS_BY_NEXT_ACTION.get(summary.get("next_action"))
    if focus == "calls":
        required_calls_today = math.ceil(required_actions_today * _REQUIRED_ACTIONS_BIAS_RATIO)
        required_messages_today = required_actions_today - required_calls_today
    elif focus == "messages":
        required_messages_today = math.ceil(required_actions_today * _REQUIRED_ACTIONS_BIAS_RATIO)
        required_calls_today = required_actions_today - required_messages_today
    else:
        required_calls_today = required_actions_today // 2
        required_messages_today = required_actions_today - required_calls_today

    return {
        "required_actions_today": required_actions_today,
        "required_calls_today": required_calls_today,
        "required_messages_today": required_messages_today,
    }


def compute_pressure_message(product_summary: dict) -> str:
    """Pressure Message (Task 4, revenue-command-center round) — the one
    sentence engineered to be impossible to ignore, worst-case first:
    a critical system_state (simplify_system_state(), above) always leads
    with "travado," even when revenue_gap alone wouldn't justify it on its
    own; otherwise a positive revenue_gap (compute_revenue_gap(), above)
    gets paired with main_action (compute_main_action(), above) so the
    money and the fix land in the same sentence; a fully on-track pipeline
    with no gap gets the calm confirmation. No new computation — every
    value here is read straight off `product_summary`."""
    gap = product_summary.get("revenue_gap", 0)
    status = product_summary.get("system_state", {}).get("status")

    if status == "critical":
        return f"Seu sistema está travado. R$ {format_brl(gap)} estão sendo perdidos agora."
    if gap > 0:
        main_action = product_summary.get("main_action", "")
        return f"Você está deixando R$ {format_brl(gap)} na mesa hoje. {main_action}"
    return "Você está no controle. Continue executando."


# compute_decision_score()'s own weights (Task 5, revenue-command-center
# round) — the round's own literal point values.
_DECISION_URGENCY_WEIGHT = 40
_DECISION_GAP_WEIGHT = 40
_DECISION_PIPELINE_WEIGHT = 20


def compute_decision_score(summary: dict) -> int:
    """Decision Priority Score (Task 5, revenue-command-center round) —
    0-100, HOW URGENT taking action is right now. Deliberately independent
    of sales_readiness_score (compute_sales_readiness(), above) — that one
    measures overall pipeline health, this one measures pressure to act
    today; collapsing them into one number would hide a healthy-but-urgent
    pipeline (or vice versa) behind a single blended figure. Built from the
    same already-counted signals every other function in this section
    reads:
      urgency (+40) — overdue_count / total_open_leads.
      revenue gap (+40) — compute_revenue_gap()'s own figure as a share of
        daily_target_revenue (no target yet, or no gap, contributes 0 from
        this term — not a penalty).
      pipeline value at stake (+20) — current_expected as a share of
        daily_target_revenue, capped at 1.0 — a large uncaptured pipeline
        sitting mostly idle is itself urgent, target-relative so it stays
        meaningful across tenants of any size. Clamped to [0, 100]."""
    total_open_leads = summary.get("total_open_leads", 0)
    overdue_ratio = (
        min(summary.get("overdue_count", 0) / total_open_leads, 1.0) if total_open_leads > 0 else 0.0
    )

    daily_target_revenue = summary.get("daily_target_revenue", 0)
    gap_ratio = (
        min(summary.get("revenue_gap", 0) / daily_target_revenue, 1.0)
        if daily_target_revenue > 0
        else 0.0
    )

    current_expected = summary.get("current_expected", 0)
    pipeline_ratio = (
        min(current_expected / daily_target_revenue, 1.0) if daily_target_revenue > 0 else 0.0
    )

    score = (
        _DECISION_URGENCY_WEIGHT * overdue_ratio
        + _DECISION_GAP_WEIGHT * gap_ratio
        + _DECISION_PIPELINE_WEIGHT * pipeline_ratio
    )
    return round(max(0, min(100, score)))


# simplify_system_state()'s own thresholds (Task 6, product-layer round) —
# the round's own literal bands.
_SYSTEM_STATE_ON_TRACK_MIN = 75
_SYSTEM_STATE_ATTENTION_MIN = 50


def simplify_system_state(product_summary: dict) -> dict:
    """Simplification Layer (Task 6, product-layer round) — collapses the
    whole product summary into the one thing a non-technical owner needs:
    "on_track"/"attention"/"critical" plus one plain-language sentence,
    driven entirely by sales_readiness_score (compute_sales_readiness(),
    above) — no second scoring pass, just banding the same number."""
    score = product_summary.get("sales_readiness_score", 0)

    if score > _SYSTEM_STATE_ON_TRACK_MIN:
        return {"status": "on_track", "message": "Você está no controle, continue assim."}
    if score >= _SYSTEM_STATE_ATTENTION_MIN:
        return {"status": "attention", "message": "Você está perdendo oportunidades importantes."}
    return {"status": "critical", "message": "Seu sistema está travado, ação imediata necessária."}


# ---------------------------------------------------------------------------
# SELF-OPTIMIZING REVENUE BRAIN (self-optimizing-revenue-brain round) —
# still no new intelligence engine: everything below mines the same
# LeadActivityLog outcomes compute_conversion_insights() (scoring.py)
# already reads, and the same already-scored `ranked` pool every function
# above already operates on. The one genuinely new data source is
# `activities` — product.py's own single bounded query over lead_lost +
# action_* rows, since no existing aggregate joins those two event
# families together. No per-industry logic anywhere.
# ---------------------------------------------------------------------------

# compute_failure_patterns()'s own vocabulary/thresholds (Task 1). Reuses
# scoring.py's own ACTION_EVENT_TYPE_TO_ACTION_TYPE (call_now/send_message/
# schedule_meeting) rather than inventing a parallel "channel" vocabulary —
# there is no channel dimension in this data model beyond action type.
_ACTION_EVENT_TYPES = frozenset(ACTION_EVENT_TYPE_TO_ACTION_TYPE)
_ACTION_TYPE_LABEL_PT = {
    "call_now": "ligações",
    "send_message": "mensagens",
    "schedule_meeting": "reuniões",
}
# A lost lead whose own time-to-loss (duration_seconds on its lead_lost
# LeadActivityLog entry, same field lead_won already carries for time-to-
# close) is at or under this many days is "early" — mirrors
# AT_RISK_STALE_AFTER_DAYS's own value (workday_engine.py) for consistency
# with this codebase's other "steady" day-based bars.
_FAILURE_TIMING_EARLY_DAYS_MAX = 3


def compute_failure_patterns(leads: list[LeadResponse], activities: dict) -> dict:
    """Failure Intelligence Engine (Task 1, self-optimizing-revenue-brain
    round) — mines already-recorded outcomes for what's NOT working, no ML.

    activities is a plain dict the caller (product.py) assembles:
      "top_loss_reason" — compute_conversion_insights()'s own figure
        (scoring.py, LOSS_REASON_MARKER technique), threaded through
        rather than re-parsed here.
      "rows" — lead_lost + action_call/action_message/action_meeting
        LeadActivityLog rows for this org (one bounded query, capped at
        product.py's own window/row limit), each
        {"lead_id", "event_type", "created_at", "duration_seconds"}.

    For every lost lead, the action_* row immediately preceding its
    lead_lost entry is "the last thing tried before it died"; the most
    common such action across all lost leads in the window is
    worst_channel (in the same call_now/send_message/schedule_meeting
    vocabulary next_best_action_type already uses — so apply_failure_
    corrections()/compute_next_best_move() can compare against it
    directly), and worst_action_pattern is that same finding as a PT
    sentence for display. failure_timing compares the average lead_lost
    duration_seconds (converted to days) against
    _FAILURE_TIMING_EARLY_DAYS_MAX: "early" means deals are dying fast (the
    fix is faster follow-up), "late" — including "no timing signal yet" —
    means deals linger before dying (the fix is more persistence, not
    urgency).

    `leads` is accepted for signature parity with this round's own spec
    and reserved for future blending (e.g. weighting patterns by the
    current pipeline's own segment mix) — not read yet."""
    rows = activities.get("rows", [])
    lost_events = [row for row in rows if row["event_type"] == "lead_lost"]

    if not lost_events:
        return {
            "top_loss_reason": activities.get("top_loss_reason"),
            "worst_action_pattern": None,
            "failure_timing": "late",
            "worst_channel": None,
        }

    actions_by_lead: dict[str, list[dict]] = {}
    for row in rows:
        if row["event_type"] in _ACTION_EVENT_TYPES:
            actions_by_lead.setdefault(row["lead_id"], []).append(row)

    last_action_counts: dict[str, int] = {}
    loss_days: list[float] = []
    for lost in lost_events:
        if lost["duration_seconds"] is not None:
            loss_days.append(lost["duration_seconds"] / 86400)

        candidates = [
            action for action in actions_by_lead.get(lost["lead_id"], [])
            if action["created_at"] <= lost["created_at"]
        ]
        if not candidates:
            continue
        last_action = max(candidates, key=lambda action: action["created_at"])
        last_action_counts[last_action["event_type"]] = (
            last_action_counts.get(last_action["event_type"], 0) + 1
        )

    worst_event_type = (
        max(last_action_counts, key=last_action_counts.get) if last_action_counts else None
    )
    worst_channel = (
        ACTION_EVENT_TYPE_TO_ACTION_TYPE.get(worst_event_type) if worst_event_type else None
    )
    worst_action_pattern = (
        f"{_ACTION_TYPE_LABEL_PT.get(worst_channel, worst_channel)} antes da perda"
        if worst_channel
        else None
    )

    avg_loss_days = sum(loss_days) / len(loss_days) if loss_days else None
    failure_timing = (
        "early"
        if avg_loss_days is not None and avg_loss_days <= _FAILURE_TIMING_EARLY_DAYS_MAX
        else "late"
    )

    return {
        "top_loss_reason": activities.get("top_loss_reason"),
        "worst_action_pattern": worst_action_pattern,
        "failure_timing": failure_timing,
        "worst_channel": worst_channel,
    }


def compute_revenue_efficiency(leads: list[LeadResponse]) -> dict:
    """Revenue Efficiency Engine (Task 3, self-optimizing-revenue-brain
    round) — pure, leads-only, no query. revenue_per_lead is the same
    expected_value-per-open-lead figure every other function in this
    module already sums; revenue_per_action divides that same total by
    chain_step (execution_engine.py's own per-lead cadence-progress
    counter, already on LeadResponse) summed across leads — the actions
    already taken on this pipeline, not a new count; conversion_efficiency
    is the average win_probability across open leads, 0-100, the same
    scale compute_sales_readiness()'s own response/execution ratios use."""
    open_leads = [lead for lead in leads if lead.status not in ("converted", "lost")]
    lead_count = len(open_leads)
    if lead_count == 0:
        return {"revenue_per_action": 0.0, "revenue_per_lead": 0.0, "conversion_efficiency": 0.0}

    total_expected_value = sum(lead.expected_value for lead in open_leads)
    total_actions_taken = sum(lead.chain_step or 0 for lead in open_leads)

    return {
        "revenue_per_action": (
            total_expected_value / total_actions_taken if total_actions_taken > 0 else 0.0
        ),
        "revenue_per_lead": total_expected_value / lead_count,
        "conversion_efficiency": sum(lead.win_probability for lead in open_leads) / lead_count,
    }


# compute_efficiency_mode()'s own bar (Task 3) — mirrors
# _HIGH_WIN_PROBABILITY_THRESHOLD (scoring.py's own constant, already
# locally mirrored above for compute_main_action()) rather than a third
# copy of the same number under a new name.
_EFFICIENCY_HIGH_CONVERSION_THRESHOLD = _HIGH_WIN_PROBABILITY_THRESHOLD


def compute_efficiency_mode(efficiency: dict) -> str:
    """Efficiency Mode (Task 3, self-optimizing-revenue-brain round) —
    "efficient"/"underutilized"/"wasteful" from compute_revenue_
    efficiency()'s own three numbers, no new signal:
      efficient — conversion_efficiency already clears the same "hot
        pipeline" bar compute_lead_score()'s own high-value-high-
        probability bonus uses. Checked first: real conversions happening
        outranks anything the other two ratios might suggest.
      underutilized — revenue_per_action >= revenue_per_lead > 0: since
        revenue_per_action divides the same total by actions taken
        (usually >= number of leads once any cadence has run), this ratio
        only reaches or exceeds revenue_per_lead when very few actions
        have been taken per lead relative to the value sitting there —
        good leads, barely worked.
      wasteful — the default: effort is going in without a
        proportionally high per-action or per-lead payoff."""
    if efficiency.get("conversion_efficiency", 0) >= _EFFICIENCY_HIGH_CONVERSION_THRESHOLD:
        return "efficient"
    if efficiency.get("revenue_per_action", 0) >= efficiency.get("revenue_per_lead", 0) > 0:
        return "underutilized"
    return "wasteful"


# compute_next_best_move()'s own copy (Task 4).
_NEXT_BEST_MOVE_BY_EFFICIENCY_MODE = {
    "underutilized": "Aumente o volume de ações agora — seus leads são bons, mas estão parados.",
    "efficient": "Dobre a aposta no seu melhor segmento — o que está funcionando, funcione mais.",
}
_ALTERNATIVE_CHANNEL_VERB_PT = {
    "call_now": "Ligue",
    "send_message": "Envie mensagem",
    "schedule_meeting": "Agende reuniões",
}


def compute_next_best_move(product_summary: dict, failure_patterns: dict, efficiency_mode: str) -> str:
    """Decision Intelligence upgrade (Task 4, self-optimizing-revenue-brain
    round) — one brutal sentence combining efficiency_mode's own directive
    (compute_efficiency_mode(), above) with an explicit "stop doing X" lead
    when failure_patterns has a worst_channel (compute_failure_patterns(),
    above) to name. "wasteful" picks the OTHER of call_now/send_message as
    the alternative channel (defaulting to call_now when there's no
    worst_channel to avoid) and reuses HIGH_VALUE_LEAD_THRESHOLD/the
    "alta probabilidade" framing compute_main_action() already uses, so
    this stays the same vocabulary a reader of that field already knows.

    `product_summary` is accepted for signature parity with this round's
    own spec and reserved for future blending (e.g. deferring to
    execution_blocked's own mandatory lead instead of the efficiency-mode
    directive) — not read yet; every signal this function currently needs
    already comes from failure_patterns/efficiency_mode."""
    worst_channel = failure_patterns.get("worst_channel")
    avoid_clause = (
        f"Pare de investir em {_ACTION_TYPE_LABEL_PT.get(worst_channel, worst_channel)}."
        if worst_channel
        else None
    )

    if efficiency_mode == "wasteful":
        alternative = "call_now" if worst_channel != "call_now" else "send_message"
        verb = _ALTERNATIVE_CHANNEL_VERB_PT.get(alternative, "Priorize")
        move = (
            f"{verb} apenas para leads acima de R$ {format_brl(HIGH_VALUE_LEAD_THRESHOLD)} "
            "com alta probabilidade — você está desperdiçando esforço."
        )
    else:
        move = _NEXT_BEST_MOVE_BY_EFFICIENCY_MODE.get(
            efficiency_mode, _NEXT_BEST_MOVE_BY_EFFICIENCY_MODE["underutilized"]
        )

    return f"{avoid_clause} {move}" if avoid_clause else move


# compute_system_health()'s own weights/bands (Task 5). readiness/
# efficiency each pull health up; urgency (decision_score) pulls it down —
# leak/overdue signals are NOT re-read here since sales_readiness_score
# already penalizes both internally (see compute_sales_readiness()'s own
# docstring) — reusing that score is the whole point, not re-penalizing
# the same two signals a second time.
_HEALTH_READINESS_WEIGHT = 0.4
_HEALTH_EFFICIENCY_WEIGHT = 0.3
_HEALTH_URGENCY_PENALTY_WEIGHT = 0.3

_SYSTEM_HEALTH_SCALING_MIN = 75
_SYSTEM_HEALTH_STABLE_MIN = 50
_SYSTEM_HEALTH_LEAKING_MIN = 25


def compute_system_health(summary: dict, efficiency: dict) -> dict:
    """System Self-Evaluation (Task 5, self-optimizing-revenue-brain
    round) — 0-100 health_score blending sales_readiness_score (summary's
    own figure, compute_sales_readiness() — already accounts for leaks and
    overdue leads internally), decision_score (summary's own urgency
    figure, compute_decision_score() — read as a penalty: high urgency
    pulls health down), and conversion_efficiency (efficiency's own
    figure, compute_revenue_efficiency() above). Banded into "scaling"/
    "stable"/"leaking"/"critical", worst-first."""
    readiness = summary.get("sales_readiness_score", 0)
    urgency = summary.get("decision_score", 0)
    conversion_efficiency = min(efficiency.get("conversion_efficiency", 0), 100)

    health_score = round(
        _HEALTH_READINESS_WEIGHT * readiness
        + _HEALTH_EFFICIENCY_WEIGHT * conversion_efficiency
        + _HEALTH_URGENCY_PENALTY_WEIGHT * (100 - urgency)
    )
    health_score = max(0, min(100, health_score))

    if health_score >= _SYSTEM_HEALTH_SCALING_MIN:
        status = "scaling"
    elif health_score >= _SYSTEM_HEALTH_STABLE_MIN:
        status = "stable"
    elif health_score >= _SYSTEM_HEALTH_LEAKING_MIN:
        status = "leaking"
    else:
        status = "critical"

    return {"health_score": health_score, "status": status}


# ---------------------------------------------------------------------------
# REVENUE OPERATING SYSTEM (revenue-operating-system round) — product
# positioning/monetization layer, not intelligence: every function below
# is a pure, O(1) lookup or arithmetic pass over the already-fully-
# assembled product_summary dict (built by routers/product.py once every
# other field above has already been computed) — no query, no per-lead
# loop, no per-industry logic. This is the layer that turns the decision
# engine above into something a prospect can be sold.
# ---------------------------------------------------------------------------

# compute_product_identity()'s own copy/lookups (Task 1). target_market
# reuses product_mode (compute_product_mode(), above) rather than
# re-deriving a market segment from raw leads; sales_complexity reuses
# system_status (compute_system_health(), above) rather than a new
# health computation.
_TARGET_MARKET_BY_PRODUCT_MODE = {
    "volume": "SMB",
    "precision": "High Ticket",
    "hybrid": "Enterprise",
}
_SALES_COMPLEXITY_BY_SYSTEM_STATUS = {
    "critical": "low",
    "leaking": "medium",
    "stable": "medium",
    "scaling": "high",
}
_PRIMARY_VALUE_PT = (
    "Substitui CRM, gestão comercial e processo de follow-up por um único "
    "sistema de decisão de receita: diz o que fazer agora, corrige a "
    "execução sozinho e mostra exatamente onde está o dinheiro."
)


def compute_product_identity(product_summary: dict) -> dict:
    """Product Identity Engine (Task 1, revenue-operating-system round) —
    pure lookup over signals already on `product_summary`, no new
    calculation. target_market reuses product_mode: volume tenants (many
    small deals) read as SMB, precision tenants (few large deals) as High
    Ticket, hybrid (both at once — the more operationally complex
    profile) as Enterprise. sales_complexity reuses system_status: a
    critical/leaking org has an obvious, easy-to-sell pain (low
    complexity); a stable/scaling org already running well needs a more
    consultative sell (medium/high)."""
    product_mode = product_summary.get("product_mode")
    system_status = product_summary.get("system_status")

    return {
        "product_category": "Revenue OS",
        "primary_value": _PRIMARY_VALUE_PT,
        "target_market": _TARGET_MARKET_BY_PRODUCT_MODE.get(product_mode, "SMB"),
        "sales_complexity": _SALES_COMPLEXITY_BY_SYSTEM_STATUS.get(system_status, "medium"),
    }


# compute_roi_estimate()'s own projection window/reference (Task 2). 30
# days keeps monthly/annual as simple, transparent multiples of the same
# daily figure (no separate "business days" assumption to justify in a
# sales conversation). _ROI_REFERENCE_MONTHLY_COST is this round's own
# literal "starter" price anchor (see compute_pricing_suggestion()'s own
# tiers below) — roi_multiple is illustrative ("this gain is worth N
# starter-plan months"), not dependent on whichever plan a given prospect
# actually ends up on.
_ROI_ESTIMATE_DAYS_PER_MONTH = 30
_ROI_REFERENCE_MONTHLY_COST = 297.0


def compute_roi_estimate(product_summary: dict) -> dict:
    """ROI Engine (Task 2, revenue-operating-system round) — projects
    today's own already-computed shortfall into a monthly/annual gain, no
    new signal: revenue_gap (compute_revenue_gap(), above — money not yet
    captured against today's own target) plus revenue_at_risk
    (compute_revenue_at_risk(), workday_engine.py — probability-weighted
    money already in the pipeline that's overdue or stale) is today's
    total recoverable upside, multiplied out to a month and a year.
    roi_multiple is that monthly figure against _ROI_REFERENCE_MONTHLY_COST,
    for a sales conversation's own "pays for itself N times over" framing."""
    daily_upside = product_summary.get("revenue_gap", 0) + product_summary.get("revenue_at_risk", 0)

    estimated_monthly_revenue_gain = daily_upside * _ROI_ESTIMATE_DAYS_PER_MONTH
    estimated_annual_revenue_gain = estimated_monthly_revenue_gain * 12
    roi_multiple = (
        round(estimated_monthly_revenue_gain / _ROI_REFERENCE_MONTHLY_COST, 1)
        if estimated_monthly_revenue_gain > 0
        else 0.0
    )

    return {
        "estimated_monthly_revenue_gain": estimated_monthly_revenue_gain,
        "estimated_annual_revenue_gain": estimated_annual_revenue_gain,
        "roi_multiple": roi_multiple,
    }


# compute_pricing_suggestion()'s own tiers (Task 3) — (plan, min monthly
# gain to qualify, monthly_price, setup_price), checked lowest-first so
# the last tier whose threshold is cleared wins. The round's own literal
# price ranges (R$297-R$1.997/mês SaaS tiers; R$5k-R$20k high-ticket
# setup).
_PRICING_TIERS = (
    ("starter", 0, 297.0, 0.0),
    ("growth", 10_000, 997.0, 5_000.0),
    ("scale", 50_000, 1_997.0, 15_000.0),
)


def compute_pricing_suggestion(product_summary: dict, roi_estimate: dict) -> dict:
    """Pricing Engine (Task 3, revenue-operating-system round) — buckets
    roi_estimate's own estimated_monthly_revenue_gain (above) into one of
    _PRICING_TIERS: a low projected gain stays a low-ticket SaaS tier
    (starter), a high one justifies a high-ticket plan with setup fee
    (scale) — "if high revenue → high ticket, if low → SaaS tier" is
    exactly this threshold ladder, not a separate calculation."""
    monthly_gain = roi_estimate.get("estimated_monthly_revenue_gain", 0)

    recommended_plan, _, monthly_price, setup_price = _PRICING_TIERS[0]
    for plan, threshold, price, setup in _PRICING_TIERS:
        if monthly_gain >= threshold:
            recommended_plan, monthly_price, setup_price = plan, price, setup

    pricing_logic = (
        f"Ganho mensal estimado de R$ {format_brl(monthly_gain)} justifica o plano "
        f"{recommended_plan} (R$ {format_brl(monthly_price)}/mês"
        + (f" + R$ {format_brl(setup_price)} de setup" if setup_price > 0 else "")
        + ")."
    )

    return {
        "recommended_plan": recommended_plan,
        "monthly_price": monthly_price,
        "setup_price": setup_price,
        "pricing_logic": pricing_logic,
    }


def generate_sales_script(product_summary: dict, roi_estimate: dict) -> str:
    """Sales Script Engine (Task 4, revenue-operating-system round) — Hook/
    Diagnosis/Opportunity/Solution/Close, built entirely from figures
    already on `product_summary`/`roi_estimate`: the hook is pressure_
    message (compute_pressure_message(), above — already the "impossible
    to ignore" sentence); the diagnosis is next_best_move
    (compute_next_best_move(), above — what this tenant is doing wrong
    right now); the opportunity is roi_estimate's own monthly/annual
    projection. Solution/close are fixed copy describing the product
    itself, not a per-tenant calculation."""
    hook = product_summary.get(
        "pressure_message", "Você está deixando dinheiro na mesa todos os dias."
    )
    diagnosis = product_summary.get("next_best_move") or product_summary.get("main_action", "")

    monthly_gain = roi_estimate.get("estimated_monthly_revenue_gain", 0)
    annual_gain = roi_estimate.get("estimated_annual_revenue_gain", 0)
    opportunity = (
        f"Isso representa até R$ {format_brl(monthly_gain)} por mês "
        f"(R$ {format_brl(annual_gain)} por ano) que você pode estar perdendo agora."
    )

    solution = (
        "O sistema decide o que fazer, corrige a execução sozinho e mostra "
        "exatamente onde está o dinheiro — todos os dias, sem depender de "
        "planilha ou achismo."
    )
    close = "Quer ver quanto disso é recuperável a partir de hoje?"

    return " ".join(part for part in (hook, diagnosis, opportunity, solution, close) if part)


def generate_objection_handlers() -> list[dict]:
    """Objection Handler (Task 5, revenue-operating-system round) — fixed
    sales copy, not derived from any tenant's data (there is no per-tenant
    signal an objection handler should vary by): the top objections this
    product category actually gets, each with a direct answer."""
    return [
        {
            "objection": "Já tenho CRM",
            "answer": (
                "Seu CRM guarda dados. Este sistema decide o que fazer com eles "
                "— ele não compete com seu CRM, ele o substitui como ferramenta "
                "de decisão."
            ),
        },
        {
            "objection": "Minha equipe já faz isso",
            "answer": (
                "Sua equipe reage ao que já aconteceu. O sistema aponta o que "
                "vai acontecer antes de você perder a venda — e corrige "
                "sozinho quando algo não está funcionando."
            ),
        },
        {
            "objection": "Não tenho tempo para implementar",
            "answer": (
                "Não há implementação manual: o sistema já lê seus leads e sua "
                "operação e devolve a próxima ação em segundos, sem processo "
                "novo para sua equipe aprender."
            ),
        },
        {
            "objection": "É caro",
            "answer": (
                "O custo é fixo; o dinheiro que você está deixando na mesa é "
                "recorrente. O ROI estimado já mostra quanto disso volta no "
                "primeiro mês."
            ),
        },
    ]
