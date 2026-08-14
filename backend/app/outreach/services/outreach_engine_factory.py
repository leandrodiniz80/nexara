from app.outreach.approval.approval_service import ApprovalService
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.render.asset_generator import AssetGenerator
from app.outreach.render.asset_renderer import AssetRenderer
from app.outreach.repositories.outreach_asset_repository import OutreachAssetRepository
from app.outreach.repositories.template_repository import TemplateRepository
from app.outreach.templates.default_templates import build_default_templates
from app.outreach.validators.message_validator import MessageValidator


def build_default_outreach_engine(
    *,
    template_repository: TemplateRepository | None = None,
    generator: AssetGenerator | None = None,
) -> OutreachEngine:
    """Composition root: wires the three mocked templates into a fresh
    TemplateRepository (unless one is given) and AssetRenderer as the default
    AssetGenerator. Swapping in a CopyAgent-backed generator later is exactly one
    argument here — see render/asset_generator.py for why nothing else changes.
    """
    template_repository = template_repository or TemplateRepository()
    if not template_repository.list_all():
        for template in build_default_templates():
            template_repository.add(template)

    return OutreachEngine(
        template_repository=template_repository,
        asset_repository=OutreachAssetRepository(),
        generator=generator or AssetRenderer(),
        validator=MessageValidator(),
        approval_service=ApprovalService(),
    )
