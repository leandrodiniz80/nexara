"""Import every domain's models here so Base.metadata is fully populated for Alembic autogenerate."""

from app.models.leads import (
    AutomationActivityLog,
    Lead,
    LeadActivityLog,
    LeadAutomation,
    LeadStatusHistory,
)
from app.models.mission import Mission, MissionEvent, MissionMetrics
from app.models.platform_auth import (
    PlatformOrganization,
    PlatformSession,
    PlatformUsage,
    PlatformUser,
    PlatformUserOrganization,
)
from app.models.prospecting import (
    Campaign,
    Company,
    CompanyTag,
    Contact,
    EmailTemplate,
    Interaction,
    Prospect,
    Tag,
)

__all__ = [
    "AutomationActivityLog",
    "Campaign",
    "Company",
    "CompanyTag",
    "Contact",
    "EmailTemplate",
    "Interaction",
    "Lead",
    "LeadActivityLog",
    "LeadAutomation",
    "LeadStatusHistory",
    "Mission",
    "MissionEvent",
    "MissionMetrics",
    "PlatformOrganization",
    "PlatformSession",
    "PlatformUsage",
    "PlatformUser",
    "PlatformUserOrganization",
    "Prospect",
    "Tag",
]
