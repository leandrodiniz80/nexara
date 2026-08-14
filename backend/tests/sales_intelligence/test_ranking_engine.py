from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.ranking.ranking_engine import RankingEngine
from app.sales_intelligence.schemas.ranked_item import RankedItem


def _item(reference: str, total_score: int) -> RankedItem:
    return RankedItem(
        reference=reference,
        score=CommercialScore(
            company_score=total_score,
            potential_score=total_score,
            urgency_score=total_score,
            visibility_score=total_score,
            relationship_score=total_score,
            conversion_probability=total_score,
            total_score=total_score,
        ),
    )


def test_sort_by_score_orders_highest_first():
    engine = RankingEngine()
    items = [_item("low", 10), _item("high", 90), _item("mid", 50)]

    ranked = engine.sort_by_score(items)

    assert [item.reference for item in ranked] == ["high", "mid", "low"]


def test_rank_companies_prospects_and_campaigns_share_the_same_sort():
    engine = RankingEngine()
    items = [_item("a", 20), _item("b", 80)]

    assert [i.reference for i in engine.rank_companies(items)] == ["b", "a"]
    assert [i.reference for i in engine.rank_prospects(items)] == ["b", "a"]
    assert [i.reference for i in engine.rank_campaigns(items)] == ["b", "a"]


def test_ranking_does_not_care_what_type_the_reference_is():
    engine = RankingEngine()
    items = [_item(reference=42, total_score=10), _item(reference={"id": "x"}, total_score=90)]

    ranked = engine.sort_by_score(items)

    assert ranked[0].reference == {"id": "x"}
    assert ranked[1].reference == 42
