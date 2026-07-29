import enum


class AgentType(str, enum.Enum):
    RESEARCH = "research"
    QUALIFICATION = "qualification"
    ENRICHMENT = "enrichment"
    SALES_STRATEGY = "sales_strategy"
    COPY = "copy"
    REVIEW = "review"
    ANALYTICS = "analytics"
