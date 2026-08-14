import uuid

from app.outreach.approval.approval_service import ApprovalService
from app.outreach.exceptions.template_exceptions import TemplateNotFoundError
from app.outreach.exceptions.transition_exceptions import InvalidMessageTransitionError
from app.outreach.exceptions.validation_exceptions import MessageValidationError
from app.outreach.models.enums import AssetType, MessageStatus
from app.outreach.models.outreach_asset import OutreachAsset
from app.outreach.render.asset_generator import AssetGenerator
from app.outreach.repositories.outreach_asset_repository import OutreachAssetRepository
from app.outreach.repositories.template_repository import TemplateRepository
from app.outreach.schemas.generation_request import GenerationRequest
from app.outreach.validators.message_validator import MessageValidator


class OutreachEngine:
    """Generates parametrized commercial assets and takes them through approval.

    Depends on `AssetGenerator` (the abstract interface), never `AssetRenderer`
    directly — that single line is what lets a future CopyAgent-backed generator be
    swapped in without this class changing (see the render/ package docs).

    OutreachEngine no longer knows what a "message" is: it only knows OutreachAsset,
    which may represent an email, a WhatsApp text, a PDF proposal, a video, or
    anything else `AssetType` names.

    Never sends anything: the terminal state this engine produces is READY_TO_SEND,
    not "sent". No SMTP, no API, no AI — every step here is deterministic.
    """

    def __init__(
        self,
        template_repository: TemplateRepository,
        asset_repository: OutreachAssetRepository,
        generator: AssetGenerator,
        validator: MessageValidator,
        approval_service: ApprovalService,
    ) -> None:
        self.template_repository = template_repository
        self.asset_repository = asset_repository
        self.generator = generator
        self.validator = validator
        self.approval_service = approval_service

    def generate_message(self, request: GenerationRequest) -> OutreachAsset:
        template = self.template_repository.get_by_id(request.template_id)
        if template is None or not template.active:
            raise TemplateNotFoundError(request.template_id)

        rendered = self.generator.generate(template, request.variables)
        return self.asset_repository.create(
            prospect_id=request.prospect_id,
            template_id=request.template_id,
            asset_type=AssetType(template.channel.value),
            channel=template.channel,
            status=MessageStatus.DRAFT,
            title=rendered.title,
            content=rendered.content,
            metadata=dict(request.variables),
            generated_by=type(self.generator).__name__,
        )

    def validate(self, asset: OutreachAsset) -> list[str]:
        template = self.template_repository.get_by_id(asset.template_id)
        if template is None:
            return [f"template {asset.template_id} no longer exists"]
        return self.validator.validate(template, asset.metadata, rendered_body=asset.content)

    def submit_for_approval(self, asset: OutreachAsset) -> OutreachAsset:
        issues = self.validate(asset)
        if issues:
            raise MessageValidationError(issues)
        return self.approval_service.submit(asset)

    def approve(
        self, asset: OutreachAsset, *, approved_by: uuid.UUID | None = None
    ) -> OutreachAsset:
        return self.approval_service.approve(asset, approved_by=approved_by)

    def reject(self, asset: OutreachAsset, *, reason: str | None = None) -> OutreachAsset:
        return self.approval_service.reject(asset, reason=reason)

    def ready_to_send(self, asset: OutreachAsset) -> OutreachAsset:
        if asset.status != MessageStatus.APPROVED:
            raise InvalidMessageTransitionError(asset.id, asset.status, "ready_to_send")
        asset.status = MessageStatus.READY_TO_SEND
        return asset
