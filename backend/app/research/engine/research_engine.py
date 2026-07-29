import csv
import io
import json
from typing import Literal

from app.research.exceptions.provider_exceptions import NoProviderAvailableError, ProviderNotAvailableError
from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.providers.base.research_provider import ResearchProvider
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.services.duplicate_detector import DuplicateDetector
from app.research.services.enrichment_pipeline import EnrichmentPipeline
from app.research.services.score_calculator import ScoreCalculator
from app.research.strategies.search_by_city_strategy import SearchByCityStrategy
from app.research.strategies.search_by_cnae_strategy import SearchByCNAEStrategy
from app.research.strategies.search_by_segment_strategy import SearchBySegmentStrategy
from app.research.strategies.search_nearby_strategy import SearchNearbyStrategy
from app.research.strategies.search_strategy import SearchStrategy

_CSV_COLUMNS = [
    "company_name",
    "trade_name",
    "cnpj",
    "website",
    "instagram",
    "linkedin",
    "phones",
    "emails",
    "address",
    "city",
    "state",
    "postal_code",
    "category",
    "subcategories",
    "rating",
    "review_count",
    "source",
    "confidence_score",
]


class ResearchEngine:
    """Discovers companies. Nothing else: no AI, no Mission, no Campaign — it doesn't
    import any of those modules and never will, by design (see the module's own
    README/docstrings). Whatever calls this engine decides what a "discovered company"
    becomes next.
    """

    def __init__(
        self,
        providers: dict[ResearchSource, ResearchProvider],
        repository: ResearchResultRepository,
        duplicate_detector: DuplicateDetector,
        enrichment_pipeline: EnrichmentPipeline,
        score_calculator: ScoreCalculator,
    ) -> None:
        self._providers = providers
        self.repository = repository
        self.duplicate_detector = duplicate_detector
        self.enrichment_pipeline = enrichment_pipeline
        self.score_calculator = score_calculator

    def _select_provider(self, source: ResearchSource | None) -> ResearchProvider:
        if source is not None:
            try:
                return self._providers[source]
            except KeyError as exc:
                raise ProviderNotAvailableError(source.value) from exc
        if not self._providers:
            raise NoProviderAvailableError()
        return next(iter(self._providers.values()))

    async def search(
        self, query: CompanySearchQuery, *, source: ResearchSource | None = None
    ) -> list[ResearchResult]:
        """Direct search entrypoint — for when the caller already has a CompanySearchQuery.
        search_by_city()/search_by_segment()/search_by_cnae()/search_nearby() build one
        for you via a SearchStrategy instead."""
        provider = self._select_provider(source)
        results = await provider.search(query)
        return self._ingest(results)

    async def _run_strategy(
        self, strategy: SearchStrategy, source: ResearchSource | None, **criteria
    ) -> list[ResearchResult]:
        provider = self._select_provider(source)
        results = await strategy.execute(provider, **criteria)
        return self._ingest(results)

    def _ingest(self, results: list[ResearchResult]) -> list[ResearchResult]:
        """Normalizes everything a provider hands back before it enters the working
        set — this is the one place EnrichmentPipeline is wired into the engine's own
        flow; validate()/enrich() stay explicit tools the caller reaches for, since
        flagging or combining results isn't something every search should do by default.
        """
        normalized = [self.enrichment_pipeline.normalize(result) for result in results]
        self.repository.add_many(normalized)
        return normalized

    async def search_by_city(
        self,
        city: str,
        state: str | None = None,
        *,
        category: str | None = None,
        source: ResearchSource | None = None,
    ) -> list[ResearchResult]:
        return await self._run_strategy(
            SearchByCityStrategy(), source, city=city, state=state, category=category
        )

    async def search_by_segment(
        self,
        segment: str,
        *,
        city: str | None = None,
        state: str | None = None,
        source: ResearchSource | None = None,
    ) -> list[ResearchResult]:
        return await self._run_strategy(
            SearchBySegmentStrategy(), source, segment=segment, city=city, state=state
        )

    async def search_by_cnae(
        self,
        cnae: str,
        *,
        city: str | None = None,
        state: str | None = None,
        source: ResearchSource | None = None,
    ) -> list[ResearchResult]:
        return await self._run_strategy(SearchByCNAEStrategy(), source, cnae=cnae, city=city, state=state)

    async def search_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        *,
        category: str | None = None,
        source: ResearchSource | None = None,
    ) -> list[ResearchResult]:
        return await self._run_strategy(
            SearchNearbyStrategy(),
            source,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            category=category,
        )

    def merge_results(self, *result_batches: list[ResearchResult]) -> list[ResearchResult]:
        """Combines multiple result batches (e.g. from different strategies/sources
        called separately) into one working list. Does not deduplicate — see
        remove_duplicates() for that."""
        merged: list[ResearchResult] = []
        for batch in result_batches:
            merged.extend(batch)
        return merged

    def remove_duplicates(self, results: list[ResearchResult]) -> list[ResearchResult]:
        """Collapses duplicate entries (the same company found by more than one
        source/search) into a single canonical record per group; untouched singles
        pass through as-is."""
        groups = self.duplicate_detector.find_duplicates(results)
        grouped_ids = {id(result) for group in groups for result in group}
        deduplicated = [self.duplicate_detector.merge(group) for group in groups]
        singles = [result for result in results if id(result) not in grouped_ids]
        return deduplicated + singles

    def calculate_scores(self, results: list[ResearchResult]) -> list[ResearchResult]:
        for result in results:
            result.confidence_score = self.score_calculator.calculate(result)
        return results

    def export(self, results: list[ResearchResult], *, fmt: Literal["json", "csv"] = "json") -> str:
        if fmt == "json":
            return json.dumps(
                [r.model_dump(mode="json") for r in results], ensure_ascii=False, indent=2
            )
        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for result in results:
                row = result.model_dump(mode="json")
                row["phones"] = ";".join(result.phones)
                row["emails"] = ";".join(result.emails)
                row["subcategories"] = ";".join(result.subcategories)
                writer.writerow(row)
            return buffer.getvalue()
        raise ValueError(f"Unsupported export format: {fmt!r}")
