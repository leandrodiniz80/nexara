from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PlatformContext(BaseModel):
    """Everything describing one Platform Kernel run — when it started, in which
    environment, and which application_version is deployed. `request_id` is set
    when the Kernel is being consulted within a specific inbound request (API/CLI)
    and left None for a long-running Worker/Scheduler process.
    """

    request_id: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    environment: str = "development"
    application_version: str = "0.1.0"
