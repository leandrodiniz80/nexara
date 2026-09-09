from __future__ import annotations

from app.services.leads.enrichment import format_brl


def generate_exec_insight(*, lost_opportunity_today: int, simulation: dict) -> str:
    """CEO Insight Layer (Task 6, Adaptive Intelligence round) — combines
    GET /workday/summary's own lost_opportunity_today (compute_lost_
    opportunity_today(), workday_engine.py — real money already being left
    on the table today, from leads with high opportunity cost) with the
    Revenue Simulation Engine's own optimistic delta (Task 5,
    simulate_revenue_if_all_actions_executed(), scoring.py) into one
    ready-to-render sentence, same "the backend writes the sentence" rule
    build_priority_reason()/focus_message/accountability_message already
    follow elsewhere in this codebase. Deterministic string composition,
    no LLM, no external AI call — just like every other message-generating
    function in this codebase.

    Kept as its own tiny module (not folded into scoring.py or
    workday_engine.py) since it's a pure orchestration/narrative layer over
    values those other modules already compute — putting it here avoids
    forcing either of them to know about this specific sentence's own
    wording, and avoids any import-direction question (this module can
    safely import from either without either needing to import back)."""
    current_expected = simulation.get("current_expected", 0)
    delta = simulation.get("delta", 0)
    percent_increase = round(delta / current_expected * 100) if current_expected > 0 else 0

    parts: list[str] = []
    if lost_opportunity_today > 0:
        parts.append(f"Você está deixando R$ {format_brl(lost_opportunity_today)} na mesa")
    if delta > 0 and percent_increase > 0:
        parts.append(
            "se executar todas as ações críticas hoje, "
            f"pode aumentar sua receita em {percent_increase}%"
        )

    if not parts:
        return "Nenhuma receita relevante sendo deixada na mesa agora — pipeline sob controle."

    return ". ".join(part[0].upper() + part[1:] for part in parts) + "."
