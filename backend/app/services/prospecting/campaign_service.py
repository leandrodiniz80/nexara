from app.repositories.prospecting.campaign_repository import CampaignRepository


class CampaignService:
    def __init__(self, repository: CampaignRepository) -> None:
        self.repository = repository
