from decimal import Decimal
from typing import ClassVar

from app.ai.providers.base import ClassificationResponse, EmbeddingResponse, ProviderResponse
from app.ai.providers.base.provider_base import ProviderBase
from app.ai.schemas.ai_context import AIMessage


class DeepSeekProvider(ProviderBase):
    """DeepSeek provider. Not implemented yet — wired up later behind this same
    interface, so nothing else in the codebase will need to change when it is."""

    provider_name: ClassVar[str] = "deepseek"

    async def generate(self, prompt: str, **kwargs) -> ProviderResponse:
        raise NotImplementedError("DeepSeekProvider.generate() is not implemented yet.")

    async def chat(self, messages: list[AIMessage], **kwargs) -> ProviderResponse:
        raise NotImplementedError("DeepSeekProvider.chat() is not implemented yet.")

    async def embed(self, text: str | list[str], **kwargs) -> EmbeddingResponse:
        raise NotImplementedError("DeepSeekProvider.embed() is not implemented yet.")

    async def classify(self, text: str, labels: list[str], **kwargs) -> ClassificationResponse:
        raise NotImplementedError("DeepSeekProvider.classify() is not implemented yet.")

    async def summarize(self, text: str, **kwargs) -> ProviderResponse:
        raise NotImplementedError("DeepSeekProvider.summarize() is not implemented yet.")

    async def extract(self, text: str, schema: dict, **kwargs) -> ProviderResponse:
        raise NotImplementedError("DeepSeekProvider.extract() is not implemented yet.")

    def estimate_tokens(self, text: str) -> int:
        raise NotImplementedError("DeepSeekProvider.estimate_tokens() is not implemented yet.")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        raise NotImplementedError("DeepSeekProvider.estimate_cost() is not implemented yet.")

    async def health_check(self) -> bool:
        raise NotImplementedError("DeepSeekProvider.health_check() is not implemented yet.")
