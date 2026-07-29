from app.repositories.prospecting.campaign_repository import CampaignRepository
from app.repositories.prospecting.company_repository import CompanyRepository
from app.repositories.prospecting.company_tag_repository import CompanyTagRepository
from app.repositories.prospecting.contact_repository import ContactRepository
from app.repositories.prospecting.email_template_repository import EmailTemplateRepository
from app.repositories.prospecting.interaction_repository import InteractionRepository
from app.repositories.prospecting.prospect_repository import ProspectRepository
from app.repositories.prospecting.tag_repository import TagRepository

__all__ = [
    "CampaignRepository",
    "CompanyRepository",
    "CompanyTagRepository",
    "ContactRepository",
    "EmailTemplateRepository",
    "InteractionRepository",
    "ProspectRepository",
    "TagRepository",
]
