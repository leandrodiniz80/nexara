from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.presentation.executive_payload import ExecutivePayload


class ResponseEnvelope(BaseModel):
    """The platform's standard public response shape — frozen, and
    completely decoupled from the domain: it only ever wraps an already-
    built ExecutivePayload (or none, on failure) plus errors/warnings and
    plain metadata. Not an API response, not JSON, not HTTP — just the
    envelope any future consumer (API, CLI, Web Dashboard, Mobile, Worker,
    SDK) is meant to receive.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    payload: ExecutivePayload | None = None
    errors: tuple[str, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)
