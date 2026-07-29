from decimal import Decimal
from typing import ClassVar

from app.ai.providers.base import ClassificationResponse, EmbeddingResponse, ProviderResponse
from app.ai.providers.base.provider_base import ProviderBase
from app.ai.schemas.ai_context import AIMessage


class GeminiProvider(ProviderBase):
    """Google (Gemini) provider. Not implemented yet — wired up later behind this same
    interface, so nothing else in the codebase will need to change when it is."""

    provider_name: ClassVar[str] = "gemini"

    async def generate(self, prompt: str, **kwargs) -> ProviderResponse:
        raise NotImplementedError("GeminiProvider.generate() is not implemented yet.")

    async def chat(self, messages: list[AIMessage], **kwargs) -> ProviderResponse:
        raise NotImplementedError("GeminiProvider.chat() is not implemented yet.")

    async def embed(self, text: str | list[str], **kwargs) -> EmbeddingResponse:
        raise NotImplementedError("GeminiProvider.embed() is not implemented yet.")

    async def classify(self, text: str, labels: list[str], **kwargs) -> ClassificationResponse:
        raise NotImplementedError("GeminiProvider.classify() is not implemented yet.")

    async def summarize(self, text: str, **kwargs) -> ProviderResponse:
        raise NotImplementedError("GeminiProvider.summarize() is not implemented yet.")

    async def extract(self, text: str, schema: dict, **kwargs) -> ProviderResponse:
        raise NotImplementedError("GeminiProvider.extract() is not implemented yet.")

    def estimate_tokens(self, text: str) -> int:
        raise NotImplementedError("GeminiProvider.estimate_tokens() is not implemented yet.")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        raise NotImplementedError("GeminiProvider.estimate_cost() is not implemented yet.")

    async def health_check(self) -> bool:
        raise NotImplementedError("GeminiProvider.health_check() is not implemented yet.")
