import uuid

from app.application.services.outreach_application_service import OutreachApplicationService
from app.outreach.models.enums import MessageStatus
from app.outreach.schemas.generation_request import GenerationRequest
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine


def _build_service():
    outreach_engine = build_default_outreach_engine()
    return OutreachApplicationService(outreach_engine), outreach_engine


async def test_generate_asset_from_template_starts_as_draft():
    service, outreach_engine = _build_service()
    template = outreach_engine.template_repository.get_active_by_category("follow_up")
    request = GenerationRequest(
        prospect_id=uuid.uuid4(),
        template_id=template.id,
        variables={"contact_name": "João", "company": "Agência XYZ"},
    )

    result = await service.generate_asset(request)

    assert result.success is True
    assert result.data.status == MessageStatus.DRAFT
    assert "João" in result.data.content


async def test_submit_for_approval_then_approve():
    service, outreach_engine = _build_service()
    template = outreach_engine.template_repository.get_active_by_category("follow_up")
    request = GenerationRequest(
        prospect_id=uuid.uuid4(),
        template_id=template.id,
        variables={"contact_name": "João", "company": "Agência XYZ"},
    )
    generated = await service.generate_asset(request)

    submitted = await service.submit_for_approval(generated.data.id)
    assert submitted.success is True
    assert submitted.data.status == MessageStatus.PENDING_APPROVAL

    approved = await service.approve(generated.data.id, approved_by=uuid.uuid4())
    assert approved.success is True
    assert approved.data.status == MessageStatus.APPROVED
    assert approved.data.approved_at is not None


async def test_reject_after_submission():
    service, outreach_engine = _build_service()
    template = outreach_engine.template_repository.get_active_by_category("follow_up")
    request = GenerationRequest(
        prospect_id=uuid.uuid4(),
        template_id=template.id,
        variables={"contact_name": "João", "company": "Agência XYZ"},
    )
    generated = await service.generate_asset(request)
    await service.submit_for_approval(generated.data.id)

    rejected = await service.reject(generated.data.id, reason="Tom incorreto")

    assert rejected.success is True
    assert rejected.data.status == MessageStatus.REJECTED


async def test_generate_asset_with_missing_template_variable_fails_gracefully():
    """"follow_up" uses both {{contact_name}} and {{company}} in its body — leaving
    "company" out makes AssetRenderer raise defensively during generate_message()
    itself (before MessageValidator ever runs); the Application Service must still
    return a failed ApplicationServiceResult, never let that exception escape."""
    service, outreach_engine = _build_service()
    template = outreach_engine.template_repository.get_active_by_category("follow_up")
    request = GenerationRequest(
        prospect_id=uuid.uuid4(),
        template_id=template.id,
        variables={"contact_name": "João"},  # missing "company"
    )

    result = await service.generate_asset(request)

    assert result.success is False
    assert result.errors != []


async def test_approve_unknown_asset_returns_failure_not_exception():
    service, _ = _build_service()

    result = await service.approve(uuid.uuid4())

    assert result.success is False
    assert any("not found" in error for error in result.errors)
