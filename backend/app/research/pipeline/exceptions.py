from app.research.exceptions.base import ResearchError


class PipelineError(ResearchError):
    """Base for Lead Discovery Pipeline failures."""


class PipelineValidationError(PipelineError):
    """Raised by ValidateRequestStep when the PipelineContext is internally inconsistent
    (e.g. a query missing the fields its own strategy requires)."""
