from app.models.prospecting.campaign import Campaign
from app.repositories.base import BaseRepository


class CampaignRepository(BaseRepository[Campaign]):
    model = Campaign
