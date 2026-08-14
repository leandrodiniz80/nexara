from typing import Any

from pydantic import BaseModel, Field


class RenderedAsset(BaseModel):
    """Output of an AssetGenerator: the rendered title/content plus generation
    metadata. OutreachEngine turns this into an OutreachAsset; the generator itself
    doesn't know that entity exists. Named title/content (not subject/body) to match
    OutreachAsset's own generalized field names.

    `metadata` was added in Sprint 10 for CopyAgent (AssetRenderer still returns an
    empty dict here) — it carries generation-time context (tone, language, model,
    etc.) that a text-substitution renderer has no equivalent of but an AI generator
    does."""

    title: str | None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
