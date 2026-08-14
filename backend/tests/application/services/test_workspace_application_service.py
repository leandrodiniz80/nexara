import uuid

from app.application.services.workspace_application_service import WorkspaceApplicationService
from app.application.workspaces.mission.mission_workspace_service import MissionWorkspaceService
from app.jobs.repositories.job_repository import JobRepository
from app.models.mission.enums import MissionPriority, MissionStatus
from app.models.prospecting.enums import (
    ProspectPriority,
    ProspectStage,
    ProspectStatus,
    ProspectTemperature,
)
from app.outreach.repositories.outreach_asset_repository import OutreachAssetRepository
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.sales_intelligence.repositories.sales_intelligence_repository import (
    SalesIntelligenceRepository,
)
from tests.application.use_cases.mission.fakes import FakeProspectRepository
from tests.application.workspaces.mission.fakes import FakeInteractionRepository
from tests.mission.fakes import (
    FakeMissionEventRepository,
    FakeMissionMetricsRepository,
    FakeMissionRepository,
)


def _build_service() -> tuple[WorkspaceApplicationService, dict]:
    mission_repo = FakeMissionRepository()
    prospect_repo = FakeProspectRepository()
    repos = dict(mission_repository=mission_repo, prospect_repository=prospect_repo)
    workspace_service = MissionWorkspaceService(
        mission_repository=mission_repo,
        mission_metrics_repository=FakeMissionMetricsRepository(),
        mission_event_repository=FakeMissionEventRepository(),
        job_repository=JobRepository(),
        prospect_repository=prospect_repo,
        research_result_repository=ResearchResultRepository(),
        sales_intelligence_repository=SalesIntelligenceRepository(),
        outreach_asset_repository=OutreachAssetRepository(),
        interaction_repository=FakeInteractionRepository(),
    )
    return WorkspaceApplicationService(workspace_service), repos


async def test_load_mission_workspace_succeeds():
    service, repos = _build_service()
    mission = await repos["mission_repository"].create(
        name="Expansão Goiânia", status=MissionStatus.RUNNING, priority=MissionPriority.NORMAL
    )

    result = await service.load_mission_workspace(mission.id)

    assert result.success is True
    assert result.data.mission.name == "Expansão Goiânia"


async def test_load_mission_workspace_unknown_mission_returns_failure():
    service, _ = _build_service()

    result = await service.load_mission_workspace(uuid.uuid4())

    assert result.success is False
    assert any("not found" in error for error in result.errors)


async def test_load_prospect_workspace_returns_the_matching_prospect():
    service, repos = _build_service()
    mission = await repos["mission_repository"].create(
        name="Expansão Goiânia", status=MissionStatus.RUNNING, priority=MissionPriority.NORMAL
    )
    prospect = await repos["prospect_repository"].create(
        mission_id=mission.id,
        company_id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        priority=ProspectPriority.NORMAL,
        status=ProspectStatus.OPEN,
        temperature=ProspectTemperature.WARM,
        current_stage=ProspectStage.NEW,
    )

    result = await service.load_prospect_workspace(mission.id, prospect.id)

    assert result.success is True
    assert result.data["prospect"].id == prospect.id
    assert result.data["mission"].id == mission.id


async def test_load_prospect_workspace_unknown_prospect_returns_failure():
    service, repos = _build_service()
    mission = await repos["mission_repository"].create(
        name="Expansão Goiânia", status=MissionStatus.RUNNING, priority=MissionPriority.NORMAL
    )

    result = await service.load_prospect_workspace(mission.id, uuid.uuid4())

    assert result.success is False
    assert any("not found" in error for error in result.errors)
