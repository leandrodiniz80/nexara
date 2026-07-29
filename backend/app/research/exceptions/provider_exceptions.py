from app.research.exceptions.base import ResearchError


class ProviderError(ResearchError):
    """Base class for research-provider failures."""


class ProviderNotAvailableError(ProviderError):
    """Raised when the engine is asked for a research source it doesn't have registered."""

    def __init__(self, source: str) -> None:
        self.source = source
        super().__init__(f"Research source '{source}' is not registered in this engine.")


class NoProviderAvailableError(ProviderError):
    def __init__(self) -> None:
        super().__init__("The Research Engine has no providers registered.")


class ProviderExecutionError(ProviderError):
    """Raised when a provider call fails (network error, API error, etc.)."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"Research provider '{source}' failed: {message}")
