from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PublicMetadata(BaseModel):
    """Metadata attached to every PublicResponse — frozen, and part of the
    platform's public contract: only what an external consumer needs to
    know about the response itself, nothing about how it was produced.
    """

    model_config = ConfigDict(frozen=True)

    application: str
    version: str
    generated_at: datetime
    request_id: str | None = None
