from typing import Any

from pydantic import BaseModel, Field

from app.research.models.enums import ResearchSource


class ResearchResult(BaseModel):
    """A company as discovered by a ResearchProvider — raw, not yet a platform Company.

    This is the Research Engine's own entity, deliberately independent of
    `app.models.prospecting.company.Company`: turning a ResearchResult into a real
    Company (dedup against the registry, assign a CNPJ-backed identity, etc.) is a
    decision for whatever calls this engine, not something Research Engine does itself
    — it doesn't know Missions or Campaigns exist, so it can't know when that
    promotion should happen.
    """

    company_name: str
    trade_name: str | None = None
    cnpj: str | None = None
    website: str | None = None
    instagram: str | None = None
    linkedin: str | None = None
    phones: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    category: str | None = None
    subcategories: list[str] = Field(default_factory=list)
    rating: float | None = None
    review_count: int | None = None
    source: ResearchSource
    confidence_score: int | None = Field(None, ge=0, le=100)
    raw_payload: dict[str, Any] | None = None
