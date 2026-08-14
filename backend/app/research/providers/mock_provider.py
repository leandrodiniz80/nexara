from typing import ClassVar

from app.research.connectors.base.connector_base import ConnectorBase
from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.providers.base.provider_base import ProviderBase
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead

# Two records always come out with a deliberately malformed email — real data quality
# issues for NormalizeCompaniesStep's validation to actually catch.
_MALFORMED_EMAIL_INDICES = (7, 21)
# The last 4 generated records are replaced with exact copies of the first 4 — a
# deterministic, guaranteed-detectable duplicate set for RemoveDuplicatesStep.
_DUPLICATE_TAIL = 4


class MockProvider(ProviderBase):
    """Deterministic, offline stand-in for a real provider — same role as
    app.ai.providers.mock_provider.MockProvider. The same CompanySearchQuery always
    produces the same results, with built-in, traceable data-quality issues (a couple
    of malformed emails) and a built-in duplicate set (the last 4 results are exact
    copies of the first 4), so the rest of the Lead Discovery Pipeline (normalize,
    dedup, score) has real, deterministic work to do — not just an empty happy path.
    """

    source: ClassVar[ResearchSource] = ResearchSource.MOCK

    def __init__(self, *, result_count: int = 20, connector: ConnectorBase | None = None) -> None:
        super().__init__(connector=connector)
        self.result_count = result_count

    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        base_name = query.category or query.segment or query.city or "Empresa"
        count = min(self.result_count, query.limit)
        results = [self._build(i, base_name, query) for i in range(count)]

        dup_start = max(0, count - _DUPLICATE_TAIL)
        for dup_index, source_index in zip(range(dup_start, count), range(_DUPLICATE_TAIL)):
            if source_index < dup_start:
                results[dup_index] = results[source_index].model_copy()
        return results

    def _build(self, index: int, base_name: str, query: CompanySearchQuery) -> ResearchResult:
        return ResearchResult(
            company_name=f"{base_name} {index + 1}",
            city=query.city,
            state=query.state,
            category=query.category or query.segment,
            website=f"https://empresa{index}.com.br" if index % 5 != 4 else None,
            emails=self._emails_for(index),
            phones=[f"6299999{index:04d}"] if index % 3 != 0 else [],
            instagram=f"@empresa{index}" if index % 2 == 0 else None,
            source=self.source,
        )

    @staticmethod
    def _emails_for(index: int) -> list[str]:
        if index in _MALFORMED_EMAIL_INDICES:
            return ["email-invalido-sem-arroba"]
        if index % 6 == 5:
            return []
        return [f"contato@empresa{index}.com.br"]

    async def get_company(self, identifier: str) -> ResearchResult | None:
        return None

    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        return []

    async def health_check(self) -> bool:
        return True
