import json
from typing import Any

from app.ai.agents.copy.copy_context_builder import CopyContext
from app.ai.exceptions.agent_exceptions import AgentExecutionError
from app.ai.providers.base.schemas import ProviderResponse
from app.outreach.render.rendered_asset import RenderedAsset


class CopyResultParser:
    """Converts a provider's raw response into a RenderedAsset.

    A well-behaved provider follows CopyPromptBuilder's "Output Format" instruction
    and returns a JSON object with title/content/metadata. Nothing guarantees that,
    though (MockProvider, used in tests, deliberately doesn't) — so anything that
    isn't parseable JSON with a `content` key falls back to treating the whole
    response as the asset's content, rather than raising.
    """

    def parse(self, response: ProviderResponse, context: CopyContext) -> RenderedAsset:
        if not response.content or not response.content.strip():
            raise AgentExecutionError("CopyAgent received an empty response from the provider.")

        parsed = self._try_parse_json(response.content)
        if parsed is not None and "content" in parsed:
            title = parsed.get("title")
            content = parsed["content"]
            extra_metadata = parsed.get("metadata")
            extra_metadata = extra_metadata if isinstance(extra_metadata, dict) else {}
        else:
            title = None
            content = response.content
            extra_metadata = {}

        metadata = {
            "asset_type": context.asset_type.value,
            "tone": context.tone,
            "communication_style": context.communication_style,
            "language": context.language,
            "model": response.model,
            **extra_metadata,
        }
        return RenderedAsset(title=title, content=content, metadata=metadata)

    @staticmethod
    def from_agent_payload(payload: dict[str, Any]) -> RenderedAsset:
        """The literal `AgentResult.payload -> RenderedAsset` conversion, for a caller
        that only has the AgentResult AIOrchestrator.execute_agent() returned."""
        return RenderedAsset(**payload)

    @staticmethod
    def _try_parse_json(text: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        return parsed if isinstance(parsed, dict) else None
