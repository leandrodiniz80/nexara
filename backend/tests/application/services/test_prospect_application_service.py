import uuid
from datetime import datetime, timezone

from app.ai.services.ai_orchestrator_factory import build_default_orchestrator
from app.application.services.prospect_application_service import ProspectApplicationService
from app.application.tasks.copy_task import CopyTask
from app.application.tasks.executors.task_executor import TaskExecutor
from app.application.tasks.qualification_task import QualificationTask
from app.outreach.models.enums import MessageStatus
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.enums import CommercialSegment, CompanySize
from app.sales_intelligence.services.sales_intelligence_engine_factory import (
    build_default_sales_intelligence_engine,
)
from app.schemas.prospecting.company import CompanyRead


def _company() -> CompanyRead:
    return CompanyRead(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        legal_name="Agência XYZ Ltda",
        trade_name="Agência XYZ",
        cnpj="12345678000199",
        segment="Publicidade",
        city="Goiânia",
        state="GO",
    )


def _build_service() -> ProspectApplicationService:
    outreach_engine = build_default_outreach_engine()
    return ProspectApplicationService(
        task_executor=TaskExecutor(),
        qualification_task=QualificationTask(build_default_sales_intelligence_engine()),
        copy_task=CopyTask(build_default_orchestrator(), outreach_engine),
        outreach_engine=outreach_engine,
    )


async def test_qualify_returns_analysis_result():
    service = _build_service()
    profile = CommercialProfile(segment=CommercialSegment.RETAIL, company_size=CompanySize.SMALL)

    result = await service.qualify(profile, company_id=uuid.uuid4())

    assert result.success is True
    assert 0 <= result.data["score"]["total_score"] <= 100


async def test_generate_asset_produces_pending_approval_asset():
    service = _build_service()

    result = await service.generate_asset(
        prospect_id=uuid.uuid4(),
        company=_company(),
        asset_type="email",
        tone="consultivo",
        contact_name="João",
        objective="Conseguir reunião",
    )

    assert result.success is True
    assert result.data["status"] == MessageStatus.PENDING_APPROVAL.value
    assert result.data["generated_by"] == "copy_agent"


async def test_approve_asset_transitions_to_approved():
    service = _build_service()
    generated = await service.generate_asset(
        prospect_id=uuid.uuid4(), company=_company(), asset_type="email"
    )
    asset_id = uuid.UUID(generated.data["id"])

    result = await service.approve_asset(asset_id, approved_by=uuid.uuid4())

    assert result.success is True
    assert result.data.status == MessageStatus.APPROVED


async def test_reject_asset_transitions_to_rejected():
    service = _build_service()
    generated = await service.generate_asset(
        prospect_id=uuid.uuid4(), company=_company(), asset_type="email"
    )
    asset_id = uuid.UUID(generated.data["id"])

    result = await service.reject_asset(asset_id, reason="Tom incorreto")

    assert result.success is True
    assert result.data.status == MessageStatus.REJECTED


async def test_approve_unknown_asset_returns_failure_not_exception():
    service = _build_service()

    result = await service.approve_asset(uuid.uuid4())

    assert result.success is False
    assert any("not found" in error for error in result.errors)
