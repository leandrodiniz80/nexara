from app.research.models.research_result import ResearchResult
from app.research.services.cnpj import is_valid_cnpj

_WEIGHTS = {
    "cnpj": 25,
    "website": 15,
    "email": 15,
    "phone": 15,
    "instagram": 10,
    "city": 10,
    "segment": 10,
}  # sums to 100


class ScoreCalculator:
    """Deterministic 0-100 confidence score from how complete a ResearchResult is.
    Same spirit as ProspectEngine.calculate_score(): an explainable heuristic, not a
    predictive model — Research Engine doesn't know AI exists.
    """

    def calculate(self, result: ResearchResult) -> int:
        score = 0
        if result.cnpj and is_valid_cnpj(result.cnpj):
            score += _WEIGHTS["cnpj"]
        if result.website:
            score += _WEIGHTS["website"]
        if result.emails:
            score += _WEIGHTS["email"]
        if result.phones:
            score += _WEIGHTS["phone"]
        if result.instagram:
            score += _WEIGHTS["instagram"]
        if result.city:
            score += _WEIGHTS["city"]
        if result.category:
            score += _WEIGHTS["segment"]
        return max(0, min(100, score))
