"""Import every domain's models here so Base.metadata is fully populated for Alembic autogenerate."""

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
    "Campaign",
    "Company",
    "CompanyTag",
    "Contact",
    "EmailTemplate",
    "Interaction",
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
