import enum


class CommercialSegment(str, enum.Enum):
    """One value per SalesStrategy subclass — this is what SalesIntelligenceEngine
    dispatches on to pick a strategy."""

    RETAIL = "retail"
    HEALTHCARE = "healthcare"
    REAL_ESTATE = "real_estate"
    AUTOMOTIVE = "automotive"
    EDUCATION = "education"
    PET = "pet"
    SHOPPING = "shopping"
    FRANCHISE = "franchise"
    CORPORATE = "corporate"


class CompanySize(str, enum.Enum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class RevenueRange(str, enum.Enum):
    """Deliberately not imported from app.models.prospecting: this module must not
    depend on Prospecting, even for a shape this similar — see the module README."""

    UNKNOWN = "unknown"
    UP_TO_360K = "up_to_360k"
    FROM_360K_TO_4_8M = "from_360k_to_4_8m"
    FROM_4_8M_TO_300M = "from_4_8m_to_300m"
    ABOVE_300M = "above_300m"


class EmployeeRange(str, enum.Enum):
    ONE_TO_10 = "1_10"
    ELEVEN_TO_50 = "11_50"
    FIFTY_ONE_TO_200 = "51_200"
    TWO_HUNDRED_ONE_TO_500 = "201_500"
    ABOVE_500 = "above_500"


class MarketingMaturity(str, enum.Enum):
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Level(str, enum.Enum):
    """Shared low/medium/high scale reused by digital_presence, website_quality,
    social_presence and competitive_level — they're all "how much of this is there"
    questions, so one enum instead of four near-identical ones."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DecisionSpeed(str, enum.Enum):
    SLOW = "slow"
    MODERATE = "moderate"
    FAST = "fast"


class GeographicScope(str, enum.Enum):
    LOCAL = "local"
    REGIONAL = "regional"
    NATIONAL = "national"
    INTERNATIONAL = "international"


class CommunicationStyle(str, enum.Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    RELATIONSHIP_DRIVEN = "relationship_driven"


class Priority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Channel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    LINKEDIN = "linkedin"
    IN_PERSON = "in_person"
