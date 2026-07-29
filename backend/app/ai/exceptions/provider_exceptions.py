from app.ai.exceptions.base import AIError


class ProviderError(AIError):
    """Base class for provider-related failures."""


class ProviderNotAvailableError(ProviderError):
    """Raised when the orchestrator is asked for a provider name it doesn't have registered."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"Provider '{provider_name}' is not registered in this orchestrator.")


class ProviderExecutionError(ProviderError):
    """Raised when a provider call fails (network error, API error, etc.)."""

    def __init__(self, provider_name: str, message: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"Provider '{provider_name}' failed: {message}")
