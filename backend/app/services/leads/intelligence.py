from __future__ import annotations

from app.schemas.leads.lead import LeadResponse
from app.schemas.performance import UserPerformanceResponse
from app.services.leads.enrichment import format_brl

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


def compute_main_action(product_summary: dict) -> str:
    """Clear Action Directive (Task 4, product-layer round) — one blunt,
    non-technical PT sentence, worst-signal-first (same severity-ordering
    precedent _build_focus_message/generate_accountability_message already
    set, workday_engine.py):
      1. overdue_count > 0 — leads already late outrank everything else.
      2. high_value_leads_without_action > 0 (detect_revenue_leaks()'s own
         signal, scoring.py) — a big deal with no next step is the next
         worst thing.
      3. next_action == "call_now" (compute_global_decision()'s own
         decision, this module) — a specific lead is mandatory right now.
      4. product_mode == "volume" (compute_product_mode(), above) — no
         single lead is on fire, but this tenant's own strategy profile
         says more outbound volume is the lever.
      5. otherwise — pipeline's under control, keep executing the plan."""
    if product_summary.get("overdue_count", 0) > 0:
        return "Foque em responder leads atrasados agora."
    if product_summary.get("high_value_leads_without_action", 0) > 0:
        return "Pare de ignorar leads de alto valor."
    if product_summary.get("next_action") == "call_now":
        return "Priorize ligações em leads quentes."
    if product_summary.get("product_mode") == "volume":
        return "Aumente volume de mensagens hoje."
    return "Continue executando o plano atual — pipeline sob controle."


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
