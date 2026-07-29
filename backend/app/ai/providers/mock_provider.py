import hashlib
from decimal import Decimal
from typing import ClassVar

from app.ai.providers.base import ClassificationResponse, EmbeddingResponse, ProviderResponse
from app.ai.providers.base.provider_base import ProviderBase
from app.ai.schemas.ai_context import AIMessage

_EMBEDDING_DIMENSIONS = 8


class MockProvider(ProviderBase):
    """Deterministic, offline stand-in for a real provider. Used in tests and local
    development so the rest of the AI module can be exercised end-to-end without any
    network call or API key. Never used to produce real product output."""

    provider_name: ClassVar[str] = "mock"

    def __init__(self, **kwargs) -> None:
        super().__init__(default_model=kwargs.pop("default_model", "mock-1"), **kwargs)

    async def generate(self, prompt: str, **kwargs) -> ProviderResponse:
        content = f"[mock:generate] {prompt[:120]}"
        return ProviderResponse(
            content=content,
            model=self.default_model,
            input_tokens=self.estimate_tokens(prompt),
            output_tokens=self.estimate_tokens(content),
            finish_reason="stop",
        )

    async def chat(self, messages: list[AIMessage], **kwargs) -> ProviderResponse:
        last_user_message = next((m.content for m in reversed(messages) if m.role == "user"), "")
        content = f"[mock:chat] {last_user_message[:120]}"
        input_tokens = sum(self.estimate_tokens(m.content) for m in messages)
        return ProviderResponse(
            content=content,
            model=self.default_model,
            input_tokens=input_tokens,
            output_tokens=self.estimate_tokens(content),
            finish_reason="stop",
        )

    async def embed(self, text: str | list[str], **kwargs) -> EmbeddingResponse:
        texts = [text] if isinstance(text, str) else text
        vectors = [self._fake_vector(t) for t in texts]
        return EmbeddingResponse(
            vectors=vectors,
            model=self.default_model,
            input_tokens=sum(self.estimate_tokens(t) for t in texts),
        )

    async def classify(self, text: str, labels: list[str], **kwargs) -> ClassificationResponse:
        if not labels:
            return ClassificationResponse(label="unknown", confidence=0.0)
        # Deterministic pick based on a hash of the text, not a real classification.
        index = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % len(labels)
        return ClassificationResponse(label=labels[index], confidence=0.5)

    async def summarize(self, text: str, **kwargs) -> ProviderResponse:
        summary = text if len(text) <= 120 else f"{text[:117]}..."
        return ProviderResponse(
            content=summary,
            model=self.default_model,
            input_tokens=self.estimate_tokens(text),
            output_tokens=self.estimate_tokens(summary),
            finish_reason="stop",
        )

    async def extract(self, text: str, schema: dict, **kwargs) -> ProviderResponse:
        content = f"[mock:extract] {list(schema.keys())}"
        return ProviderResponse(
            content=content,
            model=self.default_model,
            input_tokens=self.estimate_tokens(text),
            output_tokens=self.estimate_tokens(content),
            finish_reason="stop",
            raw={"schema_keys": list(schema.keys())},
        )

    def estimate_tokens(self, text: str) -> int:
        # ~4 chars/token is the usual ballpark heuristic for English/Portuguese text.
        return max(1, len(text) // 4)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        return Decimal("0.00")

    async def health_check(self) -> bool:
        return True

    @staticmethod
    def _fake_vector(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [byte / 255 for byte in digest[:_EMBEDDING_DIMENSIONS]]
