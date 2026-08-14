from app.sales_intelligence.models.enums import (
    CommercialSegment,
    DecisionSpeed,
    Level,
    MarketingMaturity,
    Priority,
)
from app.sales_intelligence.rules.rule import Rule

# The four rules given verbatim in the spec, plus three analogous ones rounding out
# the remaining profile fields. `facts["city"]` isn't a CommercialProfile field — it's
# the kind of ad-hoc extra_facts context build_facts() merges in when the caller has it.


def build_default_rules() -> list[Rule]:
    return [
        Rule(
            name="shopping_segment_bonus",
            condition=lambda facts: facts.get("segment") == CommercialSegment.SHOPPING,
            effect={"company_score": 20},
        ),
        Rule(
            name="high_website_quality_visibility",
            condition=lambda facts: facts.get("website_quality") == Level.HIGH,
            effect={"visibility_score": 10},
        ),
        Rule(
            name="no_social_presence_hurts_relationship",
            condition=lambda facts: facts.get("social_presence") == Level.NONE,
            effect={"relationship_score": -5},
        ),
        Rule(
            name="goiania_priority_boost",
            condition=lambda facts: facts.get("city") == "Goiânia",
            effect={"priority": Priority.HIGH.value},
        ),
        Rule(
            name="low_marketing_maturity_potential",
            condition=lambda facts: facts.get("marketing_maturity") == MarketingMaturity.NONE,
            effect={"potential_score": 15},
        ),
        Rule(
            name="fast_decision_speed_urgency",
            condition=lambda facts: facts.get("decision_speed") == DecisionSpeed.FAST,
            effect={"urgency_score": 15},
        ),
        Rule(
            name="high_competition_urgency",
            condition=lambda facts: facts.get("competitive_level") == Level.HIGH,
            effect={"urgency_score": 10},
        ),
    ]
