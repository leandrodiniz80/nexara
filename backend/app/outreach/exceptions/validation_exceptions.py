from app.outreach.exceptions.base import OutreachError


class MessageValidationError(OutreachError):
    """Raised by OutreachEngine.submit_for_approval() when MessageValidator finds
    issues — an asset never moves to PENDING_APPROVAL while invalid."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__(f"Message failed validation: {'; '.join(issues)}")
