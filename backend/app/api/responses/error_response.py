from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """One error, shaped for an API client — never a Python traceback, never a raw
    exception message with internal file paths. `code` is a stable, machine-readable
    identifier (e.g. "not_found", "validation_error"); `message` is human-readable;
    `details` carries whatever structured context is safe to expose (which field
    failed, which id wasn't found)."""

    code: str
    message: str
    details: Any | None = None
