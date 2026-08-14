import pytest

from app.sales_intelligence.exceptions.strategy_exceptions import StrategyNotFoundError
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.enums import CommercialSegment, CompanySize, Level
from app.sales_intelligence.schemas.ranked_item import RankedItem
from app.sales_intelligence.services.sales_intelligence_engine_factory import (
    build_default_sales_intelligence_engine,
)


def _profile(**overrides) -> CommercialProfile:
    defaults = dict(segment=CommercialSegment.PET, company_size=CompanySize.SMALL)
    defaults.update(overrides)
    return CommercialProfile(**defaults)


def test_analyze_company_returns_a_fully_assembled_result_and_stores_it_by_reference():
    engine = build_default_sales_intelligence_engine()
    profile = _profile()

    result = engine.analyze_company(profile, reference="company-1")

    assert result.strategy_used == CommercialSegment.PET
    assert 0 <= result.score.total_score <= 100
    assert len(result.recommendations) == 4  # 3 generic + 1 PetStrategy flavor
    assert engine.repository.get("company-1") is result


def test_analyze_prospect_is_the_same_operation_as_analyze_company():
    engine = build_default_sales_intelligence_engine()
    profile = _profile()

    company_result = engine.analyze_company(profile)
    prospect_result = engine.analyze_prospect(profile)

    # Recommendation.generated_at is a live timestamp, so two separate calls never
    # produce byte-identical Recommendation objects — compare content, not identity.
    assert company_result.score == prospect_result.score
    assert [r.title for r in company_result.recommendations] == [
        r.title for r in prospect_result.recommendations
    ]


def test_analyze_company_raises_for_an_unregistered_segment():
    engine = build_default_sales_intelligence_engine()
    engine.strategies.pop(CommercialSegment.PET)

    with pytest.raises(StrategyNotFoundError):
        engine.analyze_company(_profile(segment=CommercialSegment.PET))


def test_rank_sorts_by_total_score_regardless_of_kind():
    engine = build_default_sales_intelligence_engine()
    weak = engine.generate_score(_profile(digital_presence=Level.NONE, website_quality=Level.NONE))
    strong_profile = _profile(
        digital_presence=Level.HIGH, website_quality=Level.HIGH, social_presence=Level.HIGH
    )
    strong = engine.generate_score(strong_profile)
    items = [
        RankedItem(reference="weak", score=weak),
        RankedItem(reference="strong", score=strong),
    ]

    ranked_companies = engine.rank(items, kind="company")
    ranked_prospects = engine.rank(items, kind="prospect")

    assert [i.reference for i in ranked_companies] == ["strong", "weak"]
    assert [i.reference for i in ranked_prospects] == ["strong", "weak"]


def test_summary_reflects_the_analysis_result():
    engine = build_default_sales_intelligence_engine()
    result = engine.analyze_company(_profile())

    summary = engine.summary(result)

    assert summary.total_score == result.score.total_score
    assert summary.conversion_probability == result.score.conversion_probability
    assert summary.recommendation_count == len(result.recommendations)
    assert summary.top_recommendation == result.recommendations[0].title
    assert str(summary.total_score) in summary.narrative
