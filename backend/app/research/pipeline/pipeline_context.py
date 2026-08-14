import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.research.models.enums import ResearchSource
from app.research.pipeline.strategy_kind import StrategyKind


class PipelineContext(BaseModel):
    """Everything one LeadDiscoveryPipeline run needs. Mutable on purpose — the
    pipeline itself stamps started_at/finished_at as it runs; nothing else changes
    after construction.
    """

    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    mission_id: uuid.UUID | None = None
    requested_by: uuid.UUID | None = None
    strategy: StrategyKind
    provider: ResearchSource | None = None
    query: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
