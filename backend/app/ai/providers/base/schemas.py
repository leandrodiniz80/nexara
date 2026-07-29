from typing import Any

from pydantic import BaseModel


class ProviderResponse(BaseModel):
    """Common return shape for generate()/chat()/summarize()/extract()."""

    content: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    raw: dict[str, Any] | None = None


class EmbeddingResponse(BaseModel):
    vectors: list[list[float]]
    model: str | None = None
    input_tokens: int | None = None


class ClassificationResponse(BaseModel):
    label: str
    confidence: float
    raw: dict[str, Any] | None = None
