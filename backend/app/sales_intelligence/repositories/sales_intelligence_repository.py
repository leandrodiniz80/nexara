from typing import Any

from app.sales_intelligence.schemas.analysis_result import AnalysisResult


class SalesIntelligenceRepository:
    """In-memory store of computed AnalysisResults, keyed by an opaque `reference`
    (same convention as RankedItem — a company id, a prospect id, anything else this
    module never interprets). No database: no migration was requested for this module,
    same reasoning as Research Engine's ResearchResultRepository — this is where
    SalesIntelligenceEngine keeps what it has already analyzed during the current
    process, so a caller can look a result back up (e.g. before re-ranking) without
    recomputing it.
    """

    def __init__(self) -> None:
        self._results: dict[Any, AnalysisResult] = {}

    def save(self, reference: Any, result: AnalysisResult) -> AnalysisResult:
        self._results[reference] = result
        return result

    def get(self, reference: Any) -> AnalysisResult | None:
        return self._results.get(reference)

    def list_all(self) -> list[AnalysisResult]:
        return list(self._results.values())

    def clear(self) -> None:
        self._results.clear()
