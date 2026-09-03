from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.models.leads.lead import Lead

# Stand-in for a real data-provider integration later — POST /leads/{id}/
# enrich and the "Auto-enrich New Lead" automation both call
# simulate_enrichment() below, so swapping in a real provider is a one-place
# change whenever that happens.
_INDUSTRIES = [
    "Technology",
    "Finance",
    "Healthcare",
    "Retail",
    "Manufacturing",
    "Education",
    "Real Estate",
    "Hospitality",
]
_COMPANY_SIZES = ["1-10", "11-50", "51-200", "201-500", "500+"]
_CITIES = [
    "São Paulo",
    "Rio de Janeiro",
    "Belo Horizonte",
    "Curitiba",
    "Porto Alegre",
    "Brasília",
    "Salvador",
    "Recife",
]

# compute_lead_score() reads these too (app/services/leads/scoring.py) — one
# definition of "what counts as high-value" shared by both, not duplicated.
HIGH_VALUE_INDUSTRIES = {"Technology", "Finance"}
LARGE_COMPANY_SIZES = {"201-500", "500+"}

# Portuguese labels for the enrichment context mentioned in next_best_action
# and the message templates below (e.g. "vi que vocês são do setor de
# tecnologia") — keyed on this file's own _INDUSTRIES/_COMPANY_SIZES, so an
# unrecognized value (there shouldn't be one) just omits the context instead
# of raising. compute_next_best_action() (scoring.py) reads these too.
INDUSTRY_PT = {
    "Technology": "tecnologia",
    "Finance": "finanças",
    "Healthcare": "saúde",
    "Retail": "varejo",
    "Manufacturing": "indústria",
    "Education": "educação",
    "Real Estate": "imóveis",
    "Hospitality": "hospitalidade",
}
COMPANY_SIZE_PT = {
    "1-10": "pequeno porte",
    "11-50": "pequeno porte",
    "51-200": "médio porte",
    "201-500": "médio porte",
    "500+": "grande porte",
}

# The three next_best_action base labels compute_next_best_action() (scoring.py)
# builds on top of (before appending its own enrichment-context suffix) —
# generate_lead_message_by_action() below matches on these same prefixes to
# pick a message tone, so the two stay in lockstep by construction rather
# than by duplicated string literals.
ACTION_FIRST_CONTACT = "Fazer primeiro contato"
ACTION_URGENT_FOLLOW_UP = "Fazer follow-up urgente"
ACTION_FOLLOW_UP = "Acompanhar lead"


def _seeded_choice(seed: str, salt: str, options: list[str]) -> str:
    """Deterministic pick keyed on the lead's own id — the same lead always
    gets the same simulated value for the same field, so clicking
    "Atualizar dados" again doesn't look like it's just reshuffling random
    fake data (it produces the same profile, same as a real provider
    re-queried on unchanged inputs would)."""
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()
    return options[int(digest, 16) % len(options)]


def simulate_enrichment(lead: Lead) -> None:
    """Fills in company_name/website only if not already set (a manually
    entered value is never overwritten), and always refreshes
    enrichment_data. Mutates `lead` in place; caller commits."""
    seed = str(lead.id)
    domain = lead.email.split("@")[-1] if "@" in lead.email else "example.com"

    if not lead.company_name:
        lead.company_name = domain.split(".")[0].replace("-", " ").title()
    if not lead.website:
        lead.website = f"https://{domain}"

    industry = _seeded_choice(seed, "industry", _INDUSTRIES)
    company_size = _seeded_choice(seed, "company_size", _COMPANY_SIZES)
    city = _seeded_choice(seed, "city", _CITIES)

    lead.enrichment_data = {
        "industry": industry,
        "company_size": company_size,
        "city": city,
        "description": (
            f"{lead.company_name} is a {company_size}-employee company in the "
            f"{industry} sector, based in {city}."
        ),
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_first_contact_message(lead: Lead, sender_email: str) -> str:
    """Template-based, no LLM yet — POST /leads/{id}/generate-message's
    entire implementation. Uses enrichment_data's industry when available
    for a more specific opener; falls back to a generic one otherwise."""
    company = lead.company_name or "sua empresa"
    industry = lead.enrichment_data.get("industry") if lead.enrichment_data else None

    if industry:
        opener = (
            f"Vi que a {company} atua no setor de {industry} e imaginei que "
            "poderíamos conversar sobre como ajudar vocês a crescer ainda mais."
        )
    else:
        opener = (
            f"Gostaria de entender melhor os desafios da {company} no momento "
            "e ver se conseguimos ajudar de alguma forma."
        )

    return (
        f"Olá {lead.name},\n\n"
        f"{opener}\n\n"
        "Você teria alguns minutos essa semana para uma conversa rápida?\n\n"
        f"Atenciosamente,\n{sender_email}"
    )


def _enrichment_context_sentence(lead: Lead) -> str:
    """Renders as ' Vi que vocês são do setor de X.' (leading space, so it
    drops straight into a paragraph) — empty string when there's no
    enrichment data or the industry isn't one of INDUSTRY_PT's known
    values."""
    if not lead.enrichment_data:
        return ""
    industry_label = INDUSTRY_PT.get(lead.enrichment_data.get("industry", ""))
    if not industry_label:
        return ""
    return f" Vi que vocês são do setor de {industry_label}."


def generate_lead_message_by_action(
    lead: Lead, action: str | None, sender_email: str
) -> str | None:
    """One template per next_best_action case instead of always writing as
    if this were the first time reaching out — a follow-up that reads like
    an introduction breaks trust. `action` is next_best_action's own value
    (compute_next_best_action(), scoring.py); matched by prefix since that
    function appends its own enrichment-context suffix on top of one of
    ACTION_FIRST_CONTACT/ACTION_URGENT_FOLLOW_UP/ACTION_FOLLOW_UP. None
    (converted/lost — nothing left to act on) returns None, same as
    next_best_action itself."""
    if action is None:
        return None

    company = lead.company_name or "sua empresa"
    context = _enrichment_context_sentence(lead)

    if action.startswith(ACTION_FIRST_CONTACT):
        body = (
            f"Gostaria de me apresentar: ajudamos empresas como a {company} a crescer."
            f"{context}\n\n"
            "Você teria alguns minutos essa semana para uma conversa rápida?"
        )
    elif action.startswith(ACTION_URGENT_FOLLOW_UP):
        body = (
            "Queria retomar nosso contato — sei que a rotina é corrida, mas não queria "
            f"deixar essa conversa parada.{context}\n\n"
            "Ainda faz sentido para vocês? Consigo me adaptar ao seu horário essa semana."
        )
    elif action.startswith(ACTION_FOLLOW_UP):
        body = (
            f"Passando para ver se faz sentido continuarmos a conversa sobre como ajudar "
            f"a {company}.{context}\n\n"
            "Sem pressa nenhuma — qualquer retorno é bem-vindo quando for conveniente para você."
        )
    else:
        return None

    return f"Olá {lead.name},\n\n{body}\n\nAtenciosamente,\n{sender_email}"
