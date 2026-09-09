from __future__ import annotations

from app.services.leads.enrichment import format_brl

# generate_exec_insight()'s own PT labels (Task 7, final round) — the
# prompt's own literal example ("Modo EXTREMO ativado", "Foque em
# LIGAÇÕES agora") is all-caps for the level/focus word specifically, not
# the whole sentence.
_AGGRESSION_LABEL_PT = {"low": "BAIXO", "medium": "MÉDIO", "high": "ALTO", "extreme": "EXTREMO"}
_FOCUS_LABEL_PT = {"calls": "LIGAÇÕES", "messages": "MENSAGENS", "meetings": "REUNIÕES"}


def generate_exec_insight(
    *,
    lost_opportunity_today: int,
    simulation: dict,
    aggression_level: str | None = None,
    global_strategy: dict | None = None,
    revenue_leaks: dict | None = None,
) -> str:
    """CEO Insight Layer (Task 6, Adaptive Intelligence round; upgraded
    Task 7, final round) — combines GET /workday/summary's own
    lost_opportunity_today (compute_lost_opportunity_today(),
    workday_engine.py) with the Revenue Simulation Engine's own optimistic
    delta (simulate_revenue_if_all_actions_executed(), scoring.py) into a
    ready-to-render sentence, same "the backend writes the sentence" rule
    build_priority_reason()/focus_message/accountability_message already
    follow. Deterministic string composition, no LLM, no external AI call.

    Final round adds three more, each its own independent sentence,
    included only when the caller actually has that signal computed
    (all three default to None — an existing caller that doesn't pass
    them keeps getting exactly the original two-sentence message, this
    function's own "additive, not a rewrite" guarantee):
      aggression_level (compute_aggression_level(), scoring.py) — "Modo
        {LEVEL} ativado," first sentence when present, since it sets the
        tone for everything that follows.
      global_strategy (compute_global_strategy()'s own {focus, reason,
        confidence} dict, scoring.py) — "Foque em {CANAL} agora."
      revenue_leaks (detect_revenue_leaks()'s own dict, scoring.py) —
        "{N} leads estão sendo ignorados" when leads_ignored_over_24h > 0.

    Kept as its own tiny module (not folded into scoring.py or
    workday_engine.py) since it's a pure orchestration/narrative layer over
    values those other modules already compute — putting it here avoids
    forcing either of them to know about this specific sentence's own
    wording, and avoids any import-direction question (this module can
    safely import from either without either needing to import back)."""
    current_expected = simulation.get("current_expected", 0)
    delta = simulation.get("delta", 0)
    percent_increase = round(delta / current_expected * 100) if current_expected > 0 else 0

    sentences: list[str] = []

    if aggression_level:
        level_label = _AGGRESSION_LABEL_PT.get(aggression_level, aggression_level.upper())
        sentences.append(f"Modo {level_label} ativado.")

    if lost_opportunity_today > 0:
        sentences.append(f"Você está perdendo R$ {format_brl(lost_opportunity_today)}.")

    if delta > 0 and percent_increase > 0:
        sentences.append(
            f"Se executar todas as ações críticas hoje, pode aumentar sua receita em {percent_increase}%."
        )

    if global_strategy and global_strategy.get("focus"):
        focus_label = _FOCUS_LABEL_PT.get(global_strategy["focus"], global_strategy["focus"].upper())
        sentences.append(f"Foque em {focus_label} agora.")

    if revenue_leaks and revenue_leaks.get("leads_ignored_over_24h"):
        count = revenue_leaks["leads_ignored_over_24h"]
        subject = "lead está" if count == 1 else "leads estão"
        sentences.append(f"{count} {subject} sendo ignorados.")

    if not sentences:
        return "Nenhuma receita relevante sendo deixada na mesa agora — pipeline sob controle."

    return " ".join(sentences)
