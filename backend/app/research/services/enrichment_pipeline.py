import re

from app.research.models.research_result import ResearchResult
from app.research.services.cnpj import is_valid_cnpj, normalize_cnpj
from app.research.services.field_merge import merge_research_results

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EnrichmentPipeline:
    """Cleans up and combines ResearchResult data. No external calls: normalize() and
    validate() are pure data-quality rules; enrich() is a deliberate merge between a
    primary find and a supplementary one (e.g. a Google Maps result enriched with an
    Instagram handle found separately) — distinct from DuplicateDetector.merge(), which
    collapses records the engine believes are accidentally the same company.
    """

    def enrich(self, primary: ResearchResult, supplementary: ResearchResult) -> ResearchResult:
        return merge_research_results(primary, supplementary)

    def normalize(self, result: ResearchResult) -> ResearchResult:
        normalized = result.model_copy(deep=True)
        if normalized.company_name:
            normalized.company_name = normalized.company_name.strip()
        if normalized.trade_name:
            normalized.trade_name = normalized.trade_name.strip()
        if normalized.cnpj:
            normalized.cnpj = normalize_cnpj(normalized.cnpj)
        if normalized.website:
            normalized.website = normalized.website.strip().lower()
        if normalized.city:
            normalized.city = normalized.city.strip()
        if normalized.state:
            normalized.state = normalized.state.strip().upper()
        normalized.emails = [e.strip().lower() for e in normalized.emails if e.strip()]
        normalized.phones = [re.sub(r"[^\d+]", "", p) for p in normalized.phones if p.strip()]
        return normalized

    def validate(self, result: ResearchResult) -> list[str]:
        """Returns a list of human-readable issues; an empty list means the result is valid."""
        issues: list[str] = []

        if not result.company_name or not result.company_name.strip():
            issues.append("company_name is required")
        if result.cnpj and not is_valid_cnpj(result.cnpj):
            issues.append(f"cnpj '{result.cnpj}' fails check-digit validation")
        if result.city and not result.state:
            issues.append("state is missing despite city being set")
        for email in result.emails:
            if not _EMAIL_PATTERN.match(email):
                issues.append(f"email '{email}' is not well-formed")

        return issues
