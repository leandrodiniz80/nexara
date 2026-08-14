from pydantic import BaseModel

from app.sales_intelligence.models.enums import (
    CommercialSegment,
    CommunicationStyle,
    CompanySize,
    DecisionSpeed,
    EmployeeRange,
    GeographicScope,
    Level,
    MarketingMaturity,
    RevenueRange,
)


class CommercialProfile(BaseModel):
    """The only input this module knows how to read. Deliberately not derived from
    Company/Prospect/ResearchResult directly — whatever calls this module (today:
    nothing; tomorrow: probably AIOrchestrator) is responsible for building one from
    whatever real data it has. This is what keeps Sales Intelligence decoupled from
    every other module: it has an opinion about what a "commercial profile" looks
    like, not about where the data behind it came from.
    """

    segment: CommercialSegment
    company_size: CompanySize
    estimated_revenue: RevenueRange = RevenueRange.UNKNOWN
    employee_range: EmployeeRange | None = None
    marketing_maturity: MarketingMaturity = MarketingMaturity.NONE
    digital_presence: Level = Level.NONE
    website_quality: Level = Level.NONE
    social_presence: Level = Level.NONE
    decision_speed: DecisionSpeed = DecisionSpeed.MODERATE
    geographic_scope: GeographicScope = GeographicScope.LOCAL
    competitive_level: Level = Level.MEDIUM
    communication_style: CommunicationStyle = CommunicationStyle.FORMAL
