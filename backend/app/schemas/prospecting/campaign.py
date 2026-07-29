import uuid
from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.prospecting.enums import CampaignChannel, CampaignStatus
from app.schemas.common import AuditSchema


class CampaignBase(BaseModel):
    mission_id: uuid.UUID
    name: str = Field(..., max_length=255)
    description: str | None = None
    objective: str | None = None
    status: CampaignStatus = CampaignStatus.DRAFT
    start_date: date | None = None
    end_date: date | None = None
    channel: CampaignChannel = CampaignChannel.EMAIL
    owner_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> "CampaignBase":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    objective: str | None = None
    status: CampaignStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    channel: CampaignChannel | None = None
    owner_id: uuid.UUID | None = None


class CampaignRead(CampaignBase, AuditSchema):
    pass
