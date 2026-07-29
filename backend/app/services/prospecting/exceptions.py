import uuid

from app.models.prospecting.enums import ProspectStatus


class ProspectDomainError(Exception):
    """Base class for Prospect Engine business-rule violations."""


class ProspectClosedError(ProspectDomainError):
    """Raised when attempting to mutate a Prospect that is no longer OPEN."""

    def __init__(self, prospect_id: uuid.UUID, status: ProspectStatus) -> None:
        self.prospect_id = prospect_id
        self.status = status
        super().__init__(f"Prospect {prospect_id} is already '{status.value}' and cannot be changed.")


class CampaignNotFoundError(ProspectDomainError):
    """Raised by create_prospect() when the given campaign_id doesn't exist — a Prospect
    always derives its mission_id from its campaign, so the campaign must be real."""

    def __init__(self, campaign_id: uuid.UUID) -> None:
        self.campaign_id = campaign_id
        super().__init__(f"Campaign {campaign_id} not found.")
