from abc import ABC, abstractmethod
from decimal import Decimal

from app.ai.providers.base.schemas import ClassificationResponse, EmbeddingResponse, ProviderResponse
from app.ai.schemas.ai_context import AIMessage


class AIProvider(ABC):
    """Contract every AI provider (OpenAI, Claude, Gemini, DeepSeek, ...) must satisfy.

    Nothing outside this module is allowed to talk to a provider directly — Services
    call AIOrchestrator, AIOrchestrator calls AIProvider. This is what makes it possible
    to swap/add providers without touching a single line of business logic.
    """

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> ProviderResponse:
        """Single-shot text generation from a prompt string."""

    @abstractmethod
    async def chat(self, messages: list[AIMessage], **kwargs) -> ProviderResponse:
        """Multi-turn conversation."""

    @abstractmethod
    async def embed(self, text: str | list[str], **kwargs) -> EmbeddingResponse:
        """Vector embedding(s) for one string or a batch of strings."""

    @abstractmethod
    async def classify(self, text: str, labels: list[str], **kwargs) -> ClassificationResponse:
        """Zero/few-shot classification of `text` into one of `labels`."""

    @abstractmethod
    async def summarize(self, text: str, **kwargs) -> ProviderResponse:
        """Condense `text` into a shorter version."""

    @abstractmethod
    async def extract(self, text: str, schema: dict, **kwargs) -> ProviderResponse:
        """Structured extraction from `text` following the given JSON `schema`."""

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Best-effort token count for `text`, without calling the provider."""

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Best-effort cost in USD for the given token counts, without calling the provider."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Whether this provider is currently reachable/usable."""
