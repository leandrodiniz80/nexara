from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PromptVersion(BaseModel):
    """One stored version of a named prompt. Exactly one version per `name` is active
    at a time (see PromptRepository.activate_version())."""

    name: str
    version: int
    content: str
    is_active: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
