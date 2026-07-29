from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.services.score_calculator import ScoreCalculator

VALID_CNPJ = "11.222.333/0001-81"
INVALID_CNPJ = "11.222.333/0001-80"


def _bare_result(**overrides) -> ResearchResult:
    defaults = dict(company_name="Empresa Teste", source=ResearchSource.GOOGLE_MAPS)
    defaults.update(overrides)
    return ResearchResult(**defaults)


def test_score_is_zero_for_the_bare_minimum_result():
    calculator = ScoreCalculator()
    assert calculator.calculate(_bare_result()) == 0


def test_score_awards_full_points_for_a_complete_result():
    calculator = ScoreCalculator()
    result = _bare_result(
        cnpj=VALID_CNPJ,
        website="https://empresa.com",
        emails=["contato@empresa.com"],
        phones=["+5511999999999"],
        instagram="@empresa",
        city="Goiânia",
        category="Pet Shop",
    )
    assert calculator.calculate(result) == 100


def test_invalid_cnpj_does_not_score_points():
    calculator = ScoreCalculator()
    result = _bare_result(cnpj=INVALID_CNPJ)
    assert calculator.calculate(result) == 0


def test_score_is_additive_per_criterion():
    calculator = ScoreCalculator()
    website_only = _bare_result(website="https://empresa.com")
    website_and_city = _bare_result(website="https://empresa.com", city="Goiânia")

    assert calculator.calculate(website_only) == 15
    assert calculator.calculate(website_and_city) == 25
