import uuid

from app.ai.services.ai_orchestrator_factory import build_default_orchestrator
from app.application.services.mission_application_service import MissionApplicationService
from app.application.tasks.copy_task import CopyTask
from app.application.tasks.executors.task_executor import TaskExecutor
from app.application.tasks.qualification_task import QualificationTask
from app.application.tasks.research_task import ResearchTask
from app.application.use_cases.mission.create_prospecting_mission import (
    CreateProspectingMissionUseCase,
)
from app.application.use_cases.mission.create_prospecting_mission_request import (
    CreateProspectingMissionRequest,
)
from app.application.workspaces.mission.mission_workspace_service import MissionWorkspaceService
from app.jobs.services.job_engine_factory import build_default_job_engine
from app.outreach.repositories.outreach_asset_repository import OutreachAssetRepository
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine
from app.research.pipeline.factory import build_default_lead_discovery_pipeline
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.sales_intelligence.repositories.sales_intelligence_repository import (
    SalesIntelligenceRepository,
)
from app.sales_intelligence.services.sales_intelligence_engine_factory import (
    build_default_sales_intelligence_engine,
)
from app.services.mission.mission_engine import MissionEngine
from app.services.mission.mission_timeline import MissionTimeline
from app.services.prospecting.prospect_engine import ProspectEngine
from tests.application.use_cases.mission.fakes import (
    FakeCampaignRepository,
    FakeCompanyRepository,
    FakeInteractionRepository,
    FakeProspectRepository,
)
from tests.application.workspaces.mission.fakes import (
    FakeInteractionRepository as FakeWorkspaceInteractionRepository,
)
from tests.mission.fakes import (
    FakeMissionEventRepository,
    FakeMissionMetricsRepository,
    FakeMissionRepository,
)


def _build_service() -> MissionApplicationService:
    mission_repo = FakeMissionRepository()
    metrics_repo = FakeMissionMetricsRepository()
    event_repo = FakeMissionEventRepository()
    prospect_repo = FakeProspectRepository()
    campaign_repo = FakeCampaignRepository()
    company_repo = FakeCompanyRepository()
    job_engine = build_default_job_engine()

    mission_engine = MissionEngine(
        mission_repo, metrics_repo, prospect_repo, MissionTimeline(event_repo)
    )
    prospect_engine = ProspectEngine(prospect_repo, FakeInteractionRepository(), campaign_repo)

    use_case = CreateProspectingMissionUseCase(
        mission_engine=mission_engine,
        job_engine=job_engine,
        company_repository=company_repo,
        campaign_repository=campaign_repo,
        prospect_engine=prospect_engine,
        task_executor=TaskExecutor(),
        research_task=ResearchTask(build_default_lead_discovery_pipeline()),
        qualification_task=QualificationTask(build_default_sales_intelligence_engine()),
        copy_task=CopyTask(build_default_orchestrator(), build_default_outreach_engine()),
    )

    workspace_service = MissionWorkspaceService(
        mission_repository=mission_repo,
        mission_metrics_repository=metrics_repo,
        mission_event_repository=event_repo,
        job_repository=job_engine.repository,
        prospect_repository=prospect_repo,
        research_result_repository=ResearchResultRepository(),
        sales_intelligence_repository=SalesIntelligenceRepository(),
        outreach_asset_repository=OutreachAssetRepository(),
        interaction_repository=FakeWorkspaceInteractionRepository(),
    )

    return MissionApplicationService(
        create_prospecting_mission_use_case=use_case,
        mission_engine=mission_engine,
        mission_workspace_service=workspace_service,
    )


def _request(**overrides) -> CreateProspectingMissionRequest:
    defaults = dict(
        mission_name="Expansão Goiânia",
        segment="Publicidade",
        city="Goiânia",
        minimum_score=0,
        asset_type="email",
        requested_by=uuid.uuid4(),
    )
    defaults.update(overrides)
    return CreateProspectingMissionRequest(**defaults)


async def test_start_prospecting_mission_succeeds():
    service = _build_service()

    result = await service.start_prospecting_mission(_request())

    assert result.success is True
    assert result.data.summary.mission.name == "Expansão Goiânia"
    assert result.errors == []


async def test_start_prospecting_mission_rejects_blank_mission_name():
    service = _build_service()

    result = await service.start_prospecting_mission(_request(mission_name="   "))

    assert result.success is False
    assert any("mission_name" in error for error in result.errors)


async def test_pause_resume_cancel_lifecycle():
    service = _build_service()
    started = await service.start_prospecting_mission(_request())
    mission_id = started.data.summary.mission.id

    # the use case leaves a freshly-created Mission in DRAFT; pause() requires
    # RUNNING, so this test moves it there directly through MissionEngine (setup,
    # not something MissionApplicationService itself exposes — starting a *new*
    # mission and resuming a *paused* one are different operations on purpose).
    draft_mission = await service.mission_engine.repository.get_by_id(mission_id)
    await service.mission_engine.start(draft_mission)

    paused = await service.pause_mission(mission_id)
    assert paused.success is True
    assert paused.data.status.value == "paused"

    resumed = await service.resume_mission(mission_id)
    assert resumed.success is True
    assert resumed.data.status.value == "running"

    cancelled = await service.cancel_mission(mission_id, reason="Cliente desistiu")
    assert cancelled.success is True
    assert cancelled.data.status.value == "cancelled"


async def test_pause_unknown_mission_returns_failure_not_exception():
    service = _build_service()

    result = await service.pause_mission(uuid.uuid4())

    assert result.success is False
    assert any("not found" in error for error in result.errors)


async def test_get_status_returns_workspace():
    service = _build_service()
    started = await service.start_prospecting_mission(_request())
    mission_id = started.data.summary.mission.id

    result = await service.get_status(mission_id)

    assert result.success is True
    assert result.data.mission.id == mission_id


async def test_get_status_unknown_mission_returns_failure():
    service = _build_service()

    result = await service.get_status(uuid.uuid4())

    assert result.success is False
