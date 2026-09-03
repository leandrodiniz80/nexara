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
