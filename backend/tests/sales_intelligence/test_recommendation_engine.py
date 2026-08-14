from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import (
    Channel,
    CommercialSegment,
    CommunicationStyle,
    CompanySize,
    GeographicScope,
    Level,
    Priority,
)
from app.sales_intelligence.recommendations.recommendation_engine import (
    RecommendationEngine,
    priority_from_score,
)


def _profile(**overrides) -> CommercialProfile:
    defaults = dict(segment=CommercialSegment.CORPORATE, company_size=CompanySize.MEDIUM)
    defaults.update(overrides)
    return CommercialProfile(**defaults)


def _score(**overrides) -> CommercialScore:
    defaults = dict(
        company_score=50,
        potential_score=50,
        urgency_score=50,
        visibility_score=50,
        relationship_score=50,
        conversion_probability=50,
        total_score=50,
    )
    defaults.update(overrides)
    return CommercialScore(**defaults)


def test_priority_from_score_thresholds():
    assert priority_from_score(_score(total_score=80)) == Priority.URGENT
    assert priority_from_score(_score(total_score=60)) == Priority.HIGH
    assert priority_from_score(_score(total_score=35)) == Priority.NORMAL
    assert priority_from_score(_score(total_score=10)) == Priority.LOW


def test_recommend_products_adds_digital_presence_package_when_missing():
    engine = RecommendationEngine()
    weak_digital = _profile(digital_presence=Level.NONE)
    products = engine.recommend_products(weak_digital)
    assert any("presença digital" in p.lower() for p in products)


def test_recommend_channel_prefers_in_person_for_local_relationship_driven():
    engine = RecommendationEngine()
    profile = _profile(
        communication_style=CommunicationStyle.RELATIONSHIP_DRIVEN,
        geographic_scope=GeographicScope.LOCAL,
    )
    assert engine.recommend_channel(profile) == Channel.IN_PERSON


def test_recommend_channel_prefers_linkedin_for_corporate():
    engine = RecommendationEngine()
    profile = _profile(
        segment=CommercialSegment.CORPORATE, communication_style=CommunicationStyle.FORMAL
    )
    assert engine.recommend_channel(profile) == Channel.LINKEDIN


def test_recommend_followup_gets_more_urgent_with_higher_urgency_score():
    engine = RecommendationEngine()
    assert engine.recommend_followup(_score(urgency_score=80)) == "Follow-up em 1 dia útil"
    assert engine.recommend_followup(_score(urgency_score=10)) == "Follow-up em 14 dias"


def test_recommend_cta_scales_with_total_score():
    engine = RecommendationEngine()
    assert "proposta" in engine.recommend_cta(_profile(), _score(total_score=90)).lower()
    assert "aquecimento" in engine.recommend_cta(_profile(), _score(total_score=10)).lower()


def test_build_recommendations_returns_three_entries_with_consistent_priority():
    engine = RecommendationEngine()
    profile = _profile()
    score = _score(total_score=80, urgency_score=80)

    recommendations = engine.build_recommendations(profile, score)

    assert len(recommendations) == 3
    assert all(r.priority == Priority.URGENT for r in recommendations)
    assert all(0 <= r.confidence <= 100 for r in recommendations)
