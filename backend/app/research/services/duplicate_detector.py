import difflib
from itertools import combinations

from app.research.models.research_result import ResearchResult
from app.research.services.cnpj import normalize_cnpj
from app.research.services.field_merge import merge_research_results

_DUPLICATE_THRESHOLD = 0.8


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())


def _normalize_domain(url: str) -> str:
    domain = (
        url.lower().strip().removeprefix("https://").removeprefix("http://").removeprefix("www.")
    )
    return domain.split("/")[0]


class DuplicateDetector:
    """Decides whether two ResearchResults describe the same real-world company, and
    collapses a group of duplicates into one canonical record.
    """

    def compare(self, a: ResearchResult, b: ResearchResult) -> float:
        """Similarity in [0, 1]. An equal, valid-looking CNPJ alone proves identity
        (returns 1.0 immediately); everything else is a blend of fuzzy signals.
        """
        if a.cnpj and b.cnpj and normalize_cnpj(a.cnpj) == normalize_cnpj(b.cnpj):
            return 1.0

        signals: list[float] = [
            difflib.SequenceMatcher(
                None, a.company_name.lower().strip(), b.company_name.lower().strip()
            ).ratio()
        ]

        if a.website and b.website:
            same_domain = _normalize_domain(a.website) == _normalize_domain(b.website)
            signals.append(1.0 if same_domain else 0.0)

        a_phones = {_normalize_phone(p) for p in a.phones}
        b_phones = {_normalize_phone(p) for p in b.phones}
        if a_phones and b_phones:
            signals.append(1.0 if a_phones & b_phones else 0.0)

        if a.city and b.city and a.state and b.state:
            # Name similarity means little across different cities/states (two
            # unrelated "Bar do João" are not the same company) — weight location in.
            same_location = (
                a.city.strip().lower() == b.city.strip().lower()
                and a.state.upper() == b.state.upper()
            )
            signals.append(1.0 if same_location else 0.0)

        return sum(signals) / len(signals)

    def find_duplicates(
        self, results: list[ResearchResult], *, threshold: float = _DUPLICATE_THRESHOLD
    ) -> list[list[ResearchResult]]:
        """Groups of 2+ results considered duplicates of each other (union-find over
        pairwise compare()). Results matching no one else are simply absent from the
        output — the caller (ResearchEngine.remove_duplicates()) keeps those as-is.
        """
        parent = list(range(len(results)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            root_i, root_j = find(i), find(j)
            if root_i != root_j:
                parent[root_j] = root_i

        for i, j in combinations(range(len(results)), 2):
            if self.compare(results[i], results[j]) >= threshold:
                union(i, j)

        groups: dict[int, list[ResearchResult]] = {}
        for index, result in enumerate(results):
            groups.setdefault(find(index), []).append(result)

        return [group for group in groups.values() if len(group) > 1]

    def merge(self, results: list[ResearchResult]) -> ResearchResult:
        """Collapses a duplicate group into one record. The highest-confidence_score
        result is the base (ties keep list order); everything else folds into it."""
        if not results:
            raise ValueError("merge() requires at least one result")

        ordered = sorted(results, key=lambda r: r.confidence_score or 0, reverse=True)
        merged = ordered[0]
        for other in ordered[1:]:
            merged = merge_research_results(merged, other)
        return merged
