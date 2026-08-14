import uuid
from typing import Any

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    """Input to OutreachEngine.generate_message() — bundles what varies per call
    (which prospect, which template, which variable values) instead of a growing
    kwargs list, same reasoning as CompanySearchQuery/CommercialProfile in the
    Research/Sales Intelligence modules."""

    prospect_id: uuid.UUID
    template_id: uuid.UUID
    variables: dict[str, Any] = Field(default_factory=dict)
    created_by: uuid.UUID | None = None
