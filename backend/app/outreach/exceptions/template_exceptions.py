import uuid

from app.outreach.exceptions.base import OutreachError


class TemplateNotFoundError(OutreachError):
    def __init__(self, template_id: uuid.UUID) -> None:
        self.template_id = template_id
        super().__init__(f"AssetTemplate {template_id} not found (or not active).")


class MissingTemplateVariableError(OutreachError):
    """Raised by AssetRenderer when a placeholder in the template has no matching
    variable — MessageValidator should normally catch this before generate() ever
    runs; this is the defensive fallback if a caller renders without validating
    first."""

    def __init__(self, template_name: str, variable: str) -> None:
        self.template_name = template_name
        self.variable = variable
        super().__init__(
            f"Template '{template_name}' requires placeholder '{{{{{variable}}}}}' "
            "which was not provided."
        )
