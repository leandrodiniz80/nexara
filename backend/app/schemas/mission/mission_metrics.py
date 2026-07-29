import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import AuditSchema


class MissionMetricsRead(AuditSchema):
    """Read-only: MissionMetrics is entirely engine-managed, no Create/Update schema."""

    mission_id: uuid.UUID
    companies_found: int = 0
    companies_qualified: int = 0
    prospects_created: int = 0
    emails_generated: int = 0
    emails_approved: int = 0
    emails_sent: int = 0
    emails_opened: int = 0
    emails_replied: int = 0
    meetings: int = 0
    proposals: int = 0
    contracts: int = 0
    won_value: Decimal = Decimal("0")
    lost_value: Decimal = Decimal("0")
    conversion_rate: float | None = Field(None, ge=0, le=100)
    response_rate: float | None = Field(None, ge=0, le=100)
    meeting_rate: float | None = Field(None, ge=0, le=100)
