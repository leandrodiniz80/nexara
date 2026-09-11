from __future__ import annotations

from app.schemas.leads.lead import LeadResponse
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
