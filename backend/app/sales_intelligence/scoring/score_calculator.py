from typing import Any

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.enums import (
    CommunicationStyle,
    CompanySize,
    DecisionSpeed,
    EmployeeRange,
    GeographicScope,
    Level,
    MarketingMaturity,
    Priority,
    RevenueRange,
)
from app.sales_intelligence.rules.default_rules import build_default_rules
from app.sales_intelligence.rules.facts import build_facts
from app.sales_intelligence.rules.rule_engine import RuleEngine

_COMPANY_SIZE_POINTS: dict[CompanySize, int] = {
    CompanySize.MICRO: 10,
    CompanySize.SMALL: 20,
    CompanySize.MEDIUM: 30,
    CompanySize.LARGE: 40,
    CompanySize.ENTERPRISE: 50,
}
_REVENUE_POINTS: dict[RevenueRange, int] = {
    RevenueRange.UNKNOWN: 0,
    RevenueRange.UP_TO_360K: 10,
    RevenueRange.FROM_360K_TO_4_8M: 20,
    RevenueRange.FROM_4_8M_TO_300M: 30,
    RevenueRange.ABOVE_300M: 40,
}
_EMPLOYEE_POINTS: dict[EmployeeRange, int] = {
    EmployeeRange.ONE_TO_10: 5,
    EmployeeRange.ELEVEN_TO_50: 10,
    EmployeeRange.FIFTY_ONE_TO_200: 15,
    EmployeeRange.TWO_HUNDRED_ONE_TO_500: 20,
    EmployeeRange.ABOVE_500: 25,
}
_LEVEL_POINTS: dict[Level, int] = {Level.NONE: 0, Level.LOW: 10, Level.MEDIUM: 20, Level.HIGH: 30}
# Inverted on purpose: a company with no marketing maturity has more room for us to
# add value than one that already has an advanced setup.
_MARKETING_MATURITY_POTENTIAL_POINTS: dict[MarketingMaturity, int] = {
    MarketingMaturity.NONE: 40,
    MarketingMaturity.BASIC: 30,
    MarketingMaturity.INTERMEDIATE: 15,
    MarketingMaturity.ADVANCED: 5,
}
_GEOGRAPHIC_SCOPE_POTENTIAL_POINTS: dict[GeographicScope, int] = {
    GeographicScope.LOCAL: 10,
    GeographicScope.REGIONAL: 20,
    GeographicScope.NATIONAL: 30,
    GeographicScope.INTERNATIONAL: 40,
}
_DECISION_SPEED_URGENCY_POINTS: dict[DecisionSpeed, int] = {
    DecisionSpeed.SLOW: 5,
    DecisionSpeed.MODERATE: 15,
    DecisionSpeed.FAST: 30,
}
_COMPETITIVE_LEVEL_URGENCY_POINTS: dict[Level, int] = {
    Level.NONE: 0,
    Level.LOW: 10,
    Level.MEDIUM: 20,
    Level.HIGH: 30,
}
_COMMUNICATION_STYLE_RELATIONSHIP_POINTS: dict[CommunicationStyle, int] = {
    CommunicationStyle.FORMAL: 10,
    CommunicationStyle.TECHNICAL: 10,
    CommunicationStyle.CASUAL: 20,
    CommunicationStyle.RELATIONSHIP_DRIVEN: 30,
}
_DECISION_SPEED_CONVERSION_POINTS: dict[DecisionSpeed, int] = {
    DecisionSpeed.SLOW: 10,
    DecisionSpeed.MODERATE: 20,
    DecisionSpeed.FAST: 30,
}
_MARKETING_MATURITY_CONVERSION_POINTS: dict[MarketingMaturity, int] = {
    MarketingMaturity.NONE: 10,
    MarketingMaturity.BASIC: 20,
    MarketingMaturity.INTERMEDIATE: 30,
    MarketingMaturity.ADVANCED: 40,
}
# Inverted on purpose too: less competition around a company makes it easier to close.
_COMPETITIVE_LEVEL_CONVERSION_POINTS: dict[Level, int] = {
    Level.NONE: 30,
    Level.LOW: 30,
    Level.MEDIUM: 20,
    Level.HIGH: 10,
}

DEFAULT_TOTAL_SCORE_WEIGHTS: dict[str, float] = {
    "company_score": 0.30,
    "potential_score": 0.25,
    "urgency_score": 0.15,
    "visibility_score": 0.15,
    "relationship_score": 0.15,
}


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


class ScoreCalculator:
    """Deterministic, rule-augmented scoring: every `calculate_*` method starts from a
    baseline derived straight from the CommercialProfile's own fields (so a profile
    matching zero rules still gets a sensible score), then layers on whatever
    RuleEngine effects apply to that specific component.

    calculate_potential()/calculate_urgency() aren't in the spec's literal method list
    for this class, but CommercialScore requires potential_score/urgency_score and no
    other method produces them — they're the minimal necessary addition, not an
    invented feature.
    """

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.rule_engine = rule_engine or RuleEngine(build_default_rules())

    def calculate_company_score(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> int:
        facts = build_facts(profile, extra_facts)
        baseline = (
            _COMPANY_SIZE_POINTS[profile.company_size]
            + _REVENUE_POINTS[profile.estimated_revenue]
            + _EMPLOYEE_POINTS.get(profile.employee_range, 0)
        )
        delta = self.rule_engine.evaluate(facts).effects.get("company_score", 0)
        return _clamp(baseline + delta)

    def calculate_potential(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> int:
        facts = build_facts(profile, extra_facts)
        baseline = (
            _MARKETING_MATURITY_POTENTIAL_POINTS[profile.marketing_maturity]
            + _GEOGRAPHIC_SCOPE_POTENTIAL_POINTS[profile.geographic_scope]
        )
        delta = self.rule_engine.evaluate(facts).effects.get("potential_score", 0)
        return _clamp(baseline + delta)

    def calculate_urgency(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> int:
        facts = build_facts(profile, extra_facts)
        baseline = (
            _DECISION_SPEED_URGENCY_POINTS[profile.decision_speed]
            + _COMPETITIVE_LEVEL_URGENCY_POINTS[profile.competitive_level]
        )
        delta = self.rule_engine.evaluate(facts).effects.get("urgency_score", 0)
        return _clamp(baseline + delta)

    def calculate_visibility(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> int:
        facts = build_facts(profile, extra_facts)
        baseline = (
            _LEVEL_POINTS[profile.digital_presence]
            + _LEVEL_POINTS[profile.website_quality]
            + _LEVEL_POINTS[profile.social_presence]
        )
        delta = self.rule_engine.evaluate(facts).effects.get("visibility_score", 0)
        return _clamp(baseline + delta)

    def calculate_relationship(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> int:
        facts = build_facts(profile, extra_facts)
        baseline = (
            _COMMUNICATION_STYLE_RELATIONSHIP_POINTS[profile.communication_style]
            + _LEVEL_POINTS[profile.social_presence]
        )
        delta = self.rule_engine.evaluate(facts).effects.get("relationship_score", 0)
        return _clamp(baseline + delta)

    def calculate_conversion_probability(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> int:
        facts = build_facts(profile, extra_facts)
        baseline = (
            _DECISION_SPEED_CONVERSION_POINTS[profile.decision_speed]
            + _MARKETING_MATURITY_CONVERSION_POINTS[profile.marketing_maturity]
            + _COMPETITIVE_LEVEL_CONVERSION_POINTS[profile.competitive_level]
        )
        delta = self.rule_engine.evaluate(facts).effects.get("conversion_probability", 0)
        return _clamp(baseline + delta)

    def calculate_priority(
        self, profile: CommercialProfile, *, extra_facts: dict[str, Any] | None = None
    ) -> Priority:
        facts = build_facts(profile, extra_facts)
        effects = self.rule_engine.evaluate(facts).effects
        if "priority" in effects:
            return Priority(effects["priority"])

        urgency = self.calculate_urgency(profile, extra_facts=extra_facts)
        if urgency >= 70:
            return Priority.URGENT
        if urgency >= 45:
            return Priority.HIGH
        if urgency >= 20:
            return Priority.NORMAL
        return Priority.LOW

    def calculate_total_score(
        self,
        *,
        company_score: int,
        potential_score: int,
        urgency_score: int,
        visibility_score: int,
        relationship_score: int,
        weights: dict[str, float] | None = None,
    ) -> int:
        """Weighted combination of the five components. `weights` lets a SalesStrategy
        emphasize what matters for its segment (e.g. retail weighting visibility
        higher) — falls back to DEFAULT_TOTAL_SCORE_WEIGHTS otherwise."""
        w = weights or DEFAULT_TOTAL_SCORE_WEIGHTS
        weighted = (
            company_score * w["company_score"]
            + potential_score * w["potential_score"]
            + urgency_score * w["urgency_score"]
            + visibility_score * w["visibility_score"]
            + relationship_score * w["relationship_score"]
        )
        return _clamp(weighted)
