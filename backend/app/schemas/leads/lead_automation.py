import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeadAutomationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: str
    name: str
    active: bool
    trigger_type: str
    trigger_from: str | None
    trigger_to: str | None
    action_type: str
    created_at: datetime


class LeadAutomationUpdate(BaseModel):
    active: bool


class AutomationActivityEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lead_id: uuid.UUID
    lead_name: str
    automation_name: str
    action_type: str
    message: str
    created_at: datetime
