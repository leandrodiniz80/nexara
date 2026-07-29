import enum


class RevenueRange(str, enum.Enum):
    UP_TO_360K = "up_to_360k"
    FROM_360K_TO_4_8M = "from_360k_to_4_8m"
    FROM_4_8M_TO_300M = "from_4_8m_to_300m"
    ABOVE_300M = "above_300m"


class ContactStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LEFT_COMPANY = "left_company"
    DO_NOT_CONTACT = "do_not_contact"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CampaignChannel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    PHONE = "phone"
    EVENT = "event"
    MULTI_CHANNEL = "multi_channel"
    OTHER = "other"


class InteractionType(str, enum.Enum):
    EMAIL = "email"
    CALL = "call"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    MEETING = "meeting"
    NOTE = "note"


class ProspectStatus(str, enum.Enum):
    """Coarse lifecycle of the opportunity, independent of the funnel position (current_stage)."""

    OPEN = "open"
    WON = "won"
    LOST = "lost"
    DISQUALIFIED = "disqualified"


class ProspectStage(str, enum.Enum):
    """Fine-grained funnel position. Only meaningful while status == OPEN."""

    NEW = "new"
    RESEARCHING = "researching"
    QUALIFIED = "qualified"
    CONTACT_READY = "contact_ready"
    EMAIL_PENDING_APPROVAL = "email_pending_approval"
    EMAIL_SENT = "email_sent"
    FOLLOW_UP = "follow_up"
    RESPONDED = "responded"
    MEETING = "meeting"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class ProspectTemperature(str, enum.Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"


class ProspectPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ProspectOrigin(str, enum.Enum):
    """How this opportunity originated. Same catalogue as the old Company.lead_source,
    moved here because the origin belongs to the sales process, not to the company record."""

    WEBSITE = "website"
    REFERRAL = "referral"
    SOCIAL_MEDIA = "social_media"
    COLD_OUTREACH = "cold_outreach"
    EVENT = "event"
    INBOUND_FORM = "inbound_form"
    PARTNER = "partner"
    OTHER = "other"
