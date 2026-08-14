from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.public_error import PublicError
from app.contracts.public_metadata import PublicMetadata
from app.contracts.public_warning import PublicWarning


class PublicResponse(BaseModel):
    """The platform's public contract — frozen, and completely independent
    of the Presentation layer: exactly what any external consumer may
    receive. `payload` stays `Any` deliberately — this contract never
    converts, serializes, or transforms it, only carries it through.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    payload: Any = None
    metadata: PublicMetadata
    errors: tuple[PublicError, ...] = Field(default_factory=tuple)
    warnings: tuple[PublicWarning, ...] = Field(default_factory=tuple)
