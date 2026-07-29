import pytest

from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.services.duplicate_detector import DuplicateDetector

VALID_CNPJ = "11.222.333/0001-81"


def _result(**overrides) -> ResearchResult:
    defaults = dict(company_name="Empresa Teste", source=ResearchSource.GOOGLE_MAPS)
    defaults.update(overrides)
    return ResearchResult(**defaults)


def test_compare_returns_1_for_matching_cnpj_even_with_different_names():
    detector = DuplicateDetector()
    a = _result(company_name="Empresa Teste LTDA", cnpj=VALID_CNPJ)
    b = _result(company_name="Empresa Teste ME", cnpj=VALID_CNPJ)

    assert detector.compare(a, b) == 1.0


def test_compare_is_low_for_unrelated_companies():
    detector = DuplicateDetector()
    a = _result(company_name="Padaria do Zé", city="Goiânia", state="GO")
    b = _result(company_name="Clínica Veterinária Amigo Fiel", city="Anápolis", state="GO")

    assert detector.compare(a, b) < 0.5


def test_find_duplicates_groups_similar_companies_and_leaves_singles_out():
    detector = DuplicateDetector()
    a = _result(company_name="Pet Shop Amigo Fiel", cnpj=VALID_CNPJ, source=ResearchSource.GOOGLE_MAPS)
    b = _result(company_name="Pet Shop Amigo Fiel", cnpj=VALID_CNPJ, source=ResearchSource.INSTAGRAM)
    c = _result(company_name="Padaria Pão Quente", city="Goiânia", state="GO")

    groups = detector.find_duplicates([a, b, c])

    assert len(groups) == 1
    assert {r.source for r in groups[0]} == {ResearchSource.GOOGLE_MAPS, ResearchSource.INSTAGRAM}


def test_merge_prefers_the_higher_confidence_result_and_unions_lists():
    detector = DuplicateDetector()
    a = _result(confidence_score=40, phones=["111"], emails=[])
    b = _result(confidence_score=90, phones=["222"], emails=["contato@teste.com"])

    merged = detector.merge([a, b])

    assert merged.confidence_score == 90
    assert set(merged.phones) == {"111", "222"}
    assert merged.emails == ["contato@teste.com"]


def test_merge_requires_at_least_one_result():
    detector = DuplicateDetector()
    with pytest.raises(ValueError):
        detector.merge([])
