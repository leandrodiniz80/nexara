from abc import ABC, abstractmethod
from typing import Any

from app.outreach.models.asset_template import AssetTemplate
from app.outreach.render.rendered_asset import RenderedAsset


class AssetGenerator(ABC):
    """Contract for "turn an AssetTemplate + variables into a RenderedAsset".

    OutreachEngine depends on this abstraction, never on AssetRenderer directly —
    that is exactly what lets a future AI-backed generator (CopyAgent) be swapped in
    later without OutreachEngine changing at all. See AssetRenderer for today's only
    implementation (deterministic text substitution), and the module's own docs for
    how the swap would work.
    """

    @abstractmethod
    def generate(self, template: AssetTemplate, variables: dict[str, Any]) -> RenderedAsset:
        """Produce the rendered title/content for `template` given `variables`."""
