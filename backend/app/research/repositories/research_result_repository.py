from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult


class ResearchResultRepository:
    """In-memory store of everything discovered in the current session.

    Not backed by a database: Research Engine has no persistence in scope yet (no
    migration was requested for this module, unlike Prospecting/Mission) — this is
    where ResearchEngine accumulates results during a search/dedup/export run. Swap in
    a DB-backed implementation later behind this same interface if that changes.
    """

    def __init__(self) -> None:
        self._results: list[ResearchResult] = []

    def add(self, result: ResearchResult) -> ResearchResult:
        self._results.append(result)
        return result

    def add_many(self, results: list[ResearchResult]) -> list[ResearchResult]:
        self._results.extend(results)
        return results

    def list_all(self) -> list[ResearchResult]:
        return list(self._results)

    def list_by_source(self, source: ResearchSource) -> list[ResearchResult]:
        return [r for r in self._results if r.source == source]

    def list_by_city(self, city: str) -> list[ResearchResult]:
        return [r for r in self._results if r.city == city]

    def clear(self) -> None:
        self._results.clear()
