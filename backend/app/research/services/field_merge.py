from typing import Any

from app.research.models.research_result import ResearchResult


def _pick(primary_value: Any, secondary_value: Any) -> Any:
    return primary_value if primary_value not in (None, "") else secondary_value


def _union(list_a: list[str], list_b: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in (*list_a, *list_b):
        if item and item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


def _max_or_none(*values: float | None) -> float | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def _max_int_or_none(*values: int | None) -> int | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def merge_research_results(primary: ResearchResult, secondary: ResearchResult) -> ResearchResult:
    """Combines two records believed to describe the same company.

    `primary` wins on scalar conflicts (it's the caller's "better" record — e.g. higher
    confidence_score, or simply the one found first); list fields are unioned;
    rating/review_count take the higher value; raw_payload keeps both, keyed by source,
    so nothing from either provider's original response is lost.

    Shared by EnrichmentPipeline.enrich() (deliberately combining two sources for the
    same company) and DuplicateDetector.merge() (collapsing a detected-duplicate group)
    — the operation is identical, only the caller's intent differs.
    """
    raw_payload: dict[str, Any] = {}
    if primary.raw_payload:
        raw_payload[primary.source.value] = primary.raw_payload
    if secondary.raw_payload:
        raw_payload.setdefault(secondary.source.value, secondary.raw_payload)

    return ResearchResult(
        company_name=_pick(primary.company_name, secondary.company_name),
        trade_name=_pick(primary.trade_name, secondary.trade_name),
        cnpj=_pick(primary.cnpj, secondary.cnpj),
        website=_pick(primary.website, secondary.website),
        instagram=_pick(primary.instagram, secondary.instagram),
        linkedin=_pick(primary.linkedin, secondary.linkedin),
        phones=_union(primary.phones, secondary.phones),
        emails=_union(primary.emails, secondary.emails),
        address=_pick(primary.address, secondary.address),
        city=_pick(primary.city, secondary.city),
        state=_pick(primary.state, secondary.state),
        postal_code=_pick(primary.postal_code, secondary.postal_code),
        category=_pick(primary.category, secondary.category),
        subcategories=_union(primary.subcategories, secondary.subcategories),
        rating=_max_or_none(primary.rating, secondary.rating),
        review_count=_max_int_or_none(primary.review_count, secondary.review_count),
        source=primary.source,
        confidence_score=primary.confidence_score,
        raw_payload=raw_payload or None,
    )
