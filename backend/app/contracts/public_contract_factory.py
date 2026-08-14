from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from app.contracts.public_error import PublicError
from app.contracts.public_metadata import PublicMetadata
from app.contracts.public_response import PublicResponse
from app.contracts.public_warning import PublicWarning

_APPLICATION_NAME = "Elevel Prospect AI"
_APPLICATION_VERSION = "1.0.0"


class PublicContractFactory:
    """Builds the platform's public contract (PublicResponse) — mirroring
    ResponseEnvelope's exact rules, no different logic, no transformation:
    success() requires a payload and carries no errors; warning() requires
    a payload and carries warnings with no errors; failure() carries no
    payload and requires errors. `payload` is never converted, serialized,
    or transformed — it stays `Any`.

    Unlike ResponseEnvelope (whose payload is always an ExecutivePayload,
    guaranteed to carry its own `generated_at`), this factory's payload is
    genuinely `Any` and cannot be assumed to carry a timestamp of its own
    — so `generated_at` is always this call's own moment in time, not
    read from the payload.

    This module knows nothing about the Presentation layer: no
    ResponseEnvelope, no ExecutivePayload, no dependency on it whatsoever.
    """

    def success(
        self,
        payload: Any,
        *,
        warnings: Sequence[PublicWarning] = (),
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> PublicResponse:
        now = now or datetime.now(timezone.utc)
        return PublicResponse(
            success=True,
            payload=payload,
            errors=(),
            warnings=tuple(warnings),
            metadata=self._metadata(now, request_id),
        )

    def warning(
        self,
        payload: Any,
        warnings: Sequence[PublicWarning],
        *,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> PublicResponse:
        now = now or datetime.now(timezone.utc)
        return PublicResponse(
            success=True,
            payload=payload,
            errors=(),
            warnings=tuple(warnings),
            metadata=self._metadata(now, request_id),
        )

    def failure(
        self,
        errors: Sequence[PublicError],
        *,
        warnings: Sequence[PublicWarning] = (),
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> PublicResponse:
        now = now or datetime.now(timezone.utc)
        return PublicResponse(
            success=False,
            payload=None,
            errors=tuple(errors),
            warnings=tuple(warnings),
            metadata=self._metadata(now, request_id),
        )

    @staticmethod
    def _metadata(generated_at: datetime, request_id: str | None) -> PublicMetadata:
        return PublicMetadata(
            application=_APPLICATION_NAME,
            version=_APPLICATION_VERSION,
            generated_at=generated_at,
            request_id=request_id,
        )
