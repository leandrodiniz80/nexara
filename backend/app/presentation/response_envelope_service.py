from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from app.presentation.executive_payload import ExecutivePayload
from app.presentation.response_envelope import ResponseEnvelope

_APPLICATION_NAME = "Elevel Prospect AI"
_APPLICATION_VERSION = "1.0.0"


class ResponseEnvelopeService:
    """Encapsulates an already-built ExecutivePayload into the platform's
    standard public response — never alters the ExecutivePayload, never
    modifies a list, never recalculates data, never converts a type; only
    wraps. No domain-module import, no Engine, no Adapter, no persistence,
    no integration, no API, no HTTP, no JSON, no serialization — just
    encapsulation.

    ExecutivePayloadService remains the only place responsible for
    building the transport DTO; this class only ever wraps an
    already-built one (or none, on failure) into a standardized response.
    """

    def success(
        self,
        payload: ExecutivePayload,
        *,
        warnings: Sequence[str] = (),
        request_id: str | None = None,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            success=True,
            payload=payload,
            errors=(),
            warnings=tuple(warnings),
            metadata=self._metadata(payload.generated_at, request_id),
        )

    def warning(
        self,
        payload: ExecutivePayload,
        warnings: Sequence[str],
        *,
        request_id: str | None = None,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            success=True,
            payload=payload,
            errors=(),
            warnings=tuple(warnings),
            metadata=self._metadata(payload.generated_at, request_id),
        )

    def failure(
        self,
        errors: Sequence[str],
        *,
        warnings: Sequence[str] = (),
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> ResponseEnvelope:
        now = now or datetime.now(timezone.utc)
        return ResponseEnvelope(
            success=False,
            payload=None,
            errors=tuple(errors),
            warnings=tuple(warnings),
            metadata=self._metadata(now, request_id),
        )

    @staticmethod
    def _metadata(generated_at: datetime, request_id: str | None) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "generated_at": generated_at,
            "version": _APPLICATION_VERSION,
            "application": _APPLICATION_NAME,
        }
        if request_id is not None:
            metadata["request_id"] = request_id
        return metadata
