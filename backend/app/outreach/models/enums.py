import enum


class Channel(str, enum.Enum):
    """Deliberately local to this module — not imported from
    app.sales_intelligence.models.enums.Channel, even though the concept is similar:
    each bounded context owns its own vocabulary rather than depending on another's."""

    EMAIL = "email"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"


class MessageStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    READY_TO_SEND = "ready_to_send"


class AssetType(str, enum.Enum):
    """What kind of commercial asset this is — broader than `Channel`, which only
    describes a delivery channel. A PROPOSAL or VIDEO may not have a channel at all;
    EMAIL/WHATSAPP/LINKEDIN overlap with Channel by value since those asset types are
    still, today, delivered through exactly the channel of the same name."""

    EMAIL = "email"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    PROPOSAL = "proposal"
    DOCUMENT = "document"
    CALL_SCRIPT = "call_script"
    TEXT = "text"
    VIDEO = "video"
    AUDIO = "audio"
