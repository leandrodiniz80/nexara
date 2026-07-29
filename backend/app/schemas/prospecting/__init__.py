from app.schemas.prospecting.campaign import CampaignBase, CampaignCreate, CampaignRead, CampaignUpdate
from app.schemas.prospecting.company import CompanyBase, CompanyCreate, CompanyRead, CompanyUpdate
from app.schemas.prospecting.company_tag import CompanyTagBase, CompanyTagCreate, CompanyTagRead
from app.schemas.prospecting.contact import ContactBase, ContactCreate, ContactRead, ContactUpdate
from app.schemas.prospecting.email_template import (
    EmailTemplateBase,
    EmailTemplateCreate,
    EmailTemplateRead,
    EmailTemplateUpdate,
)
from app.schemas.prospecting.interaction import (
    InteractionBase,
    InteractionCreate,
    InteractionRead,
    InteractionUpdate,
)
from app.schemas.prospecting.prospect import ProspectBase, ProspectCreate, ProspectRead, ProspectUpdate
from app.schemas.prospecting.tag import TagBase, TagCreate, TagRead, TagUpdate

__all__ = [
    "CampaignBase",
    "CampaignCreate",
    "CampaignRead",
    "CampaignUpdate",
    "CompanyBase",
    "CompanyCreate",
    "CompanyRead",
    "CompanyUpdate",
    "CompanyTagBase",
    "CompanyTagCreate",
    "CompanyTagRead",
    "ContactBase",
    "ContactCreate",
    "ContactRead",
    "ContactUpdate",
    "EmailTemplateBase",
    "EmailTemplateCreate",
    "EmailTemplateRead",
    "EmailTemplateUpdate",
    "InteractionBase",
    "InteractionCreate",
    "InteractionRead",
    "InteractionUpdate",
    "ProspectBase",
    "ProspectCreate",
    "ProspectRead",
    "ProspectUpdate",
    "TagBase",
    "TagCreate",
    "TagRead",
    "TagUpdate",
]
