from app.contracts.public_error import PublicError
from app.contracts.public_metadata import PublicMetadata
from app.contracts.public_response import PublicResponse
from app.contracts.public_warning import PublicWarning
from app.presentation.response_envelope import ResponseEnvelope

_GENERIC_ERROR_CODE = "ERROR"
_GENERIC_WARNING_CODE = "WARNING"


class ResponseMapper:
    """THE SINGLE, EXPLICITLY AUTHORIZED EXCEPTION IN THIS PLATFORM'S
    ARCHITECTURE: this is the only file allowed to import both
    `app.presentation` (ResponseEnvelope) and `app.contracts`
    (PublicResponse) at the same time. Presentation and Contracts are two
    completely independent worlds — no other class anywhere in the
    platform may know both types simultaneously. This mapper exists solely
    to bridge them.

    `to_public_response()` never alters `payload`, never recalculates
    anything, never converts a type, never serializes, never modifies a
    list — it only copies. `ResponseEnvelope.errors`/`.warnings` are plain
    `tuple[str, ...]` with no structured code of their own, while
    `PublicError`/`PublicWarning` require both a `code` and a `message`;
    since there is no per-item code to copy, each mapped item uses a fixed
    platform-wide category code ("ERROR"/"WARNING") and carries the
    original string through, verbatim, as `message` — no code is invented
    or derived from the message's content.
    """

    def to_public_response(self, response: ResponseEnvelope) -> PublicResponse:
        metadata = response.metadata
        return PublicResponse(
            success=response.success,
            payload=response.payload,
            metadata=PublicMetadata(
                application=metadata.get("application"),
                version=metadata.get("version"),
                generated_at=metadata.get("generated_at"),
                request_id=metadata.get("request_id"),
            ),
            errors=tuple(
                PublicError(code=_GENERIC_ERROR_CODE, message=message)
                for message in response.errors
            ),
            warnings=tuple(
                PublicWarning(code=_GENERIC_WARNING_CODE, message=message)
                for message in response.warnings
            ),
        )
