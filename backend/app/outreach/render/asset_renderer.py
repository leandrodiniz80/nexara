from typing import Any

from app.outreach.exceptions.template_exceptions import MissingTemplateVariableError
from app.outreach.models.asset_template import AssetTemplate
from app.outreach.render.asset_generator import AssetGenerator
from app.outreach.render.placeholders import substitute
from app.outreach.render.rendered_asset import RenderedAsset


class AssetRenderer(AssetGenerator):
    """Deterministic, parametrized-template substitution — no AI. Receives an
    AssetTemplate and a dict of variables, replaces every `{{placeholder}}` in
    `subject`/`body` with the matching variable's string value.
    """

    def generate(self, template: AssetTemplate, variables: dict[str, Any]) -> RenderedAsset:
        def _missing(key: str) -> str:
            raise MissingTemplateVariableError(template.name, key)

        title = (
            substitute(template.subject, variables, on_missing=_missing)
            if template.subject
            else None
        )
        content = substitute(template.body, variables, on_missing=_missing)
        return RenderedAsset(title=title, content=content)
