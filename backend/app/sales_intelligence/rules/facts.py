from typing import Any

from app.sales_intelligence.models.commercial_profile import CommercialProfile


def build_facts(
    profile: CommercialProfile, extra_facts: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The dict every Rule condition actually sees: the profile's own fields (as enum
    members, not strings — model_dump()'s default `mode="python"`) plus whatever extra
    ad-hoc context the caller supplied (e.g. `city="Goiânia"` — not a CommercialProfile
    field, but still something a rule can reasonably key off of).
    """
    facts = profile.model_dump()
    if extra_facts:
        facts.update(extra_facts)
    return facts
