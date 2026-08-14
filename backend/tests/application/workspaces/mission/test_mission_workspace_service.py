import uuid
from datetime import date, datetime, timedelta, timezone

from app.application.workspaces.mission.mission_workspace_query import MissionWorkspaceQuery
from app.application.workspaces.mission.mission_workspace_service import MissionWorkspaceService
from app.jobs.models.enums import JobStatus
from app.jobs.repositories.job_repository import JobRepository
from app.models.mission.enums import MissionPriority, MissionStatus
from app.models.prospecting.enums import (
    InteractionType,
    ProspectPriority,
    ProspectStage,
    ProspectStatus,
    ProspectTemperature,
)
from app.outreach.models.enums import AssetType, Channel, MessageStatus
from app.outreach.repositories.outreach_asset_repository import OutreachAssetRepository
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment, CompanySize, Priority
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.repositories.sales_intelligence_repository import (
    SalesIntelligenceRepository,
)
from app.sales_intelligence.schemas.analysis_result import AnalysisResult
from app.schemas.mission.enums import PipelineHealth
from tests.application.use_cases.mission.fakes import FakeProspectRepository
from tests.application.workspaces.mission.fakes import FakeInteractionRepository
from tests.mission.fakes import (
    FakeMissionEventRepository,
    FakeMissionMetricsRepository,
    FakeMissionRepository,
)


def _build_service(**repos) -> tuple[MissionWorkspaceService, dict]:
    defaults = dict(
        mission_repository=FakeMissionRepository(),
        mission_metrics_repository=FakeMissionMetricsRepository(),
        mission_event_repository=FakeMissionEventRepository(),
        job_repository=JobRepository(),
        prospect_repository=FakeProspectRepository(),
        research_result_repository=ResearchResultRepository(),
        sales_intelligence_repository=SalesIntelligenceRepository(),
        outreach_asset_repository=OutreachAssetRepository(),
        interaction_repository=FakeInteractionRepository(),
    )
    defaults.update(repos)
    return MissionWorkspaceService(**defaults), defaults


async def test_load_returns_none_for_unknown_mission():
    service, _ = _build_service()

    workspace = await service.load(MissionWorkspaceQuery(mission_id=uuid.uuid4()))

    assert workspace is None


async def test_load_for_mission_with_no_prospects():
    service, repos = _build_service()
    mission = await repos["mission_repository"].create(
        name="Missão Vazia",
        status=MissionStatus.DRAFT,
        priority=MissionPriority.NORMAL,
        progress=0,
        target_city="Goiânia",
    )
    await repos["mission_metrics_repository"].create(mission_id=mission.id)

    workspace = await service.load(MissionWorkspaceQuery(mission_id=mission.id))

    assert workspace is not None
    assert workspace.mission.name == "Missão Vazia"
    assert workspace.statistics.companies_found == 0
    assert workspace.statistics.prospects == 0
    assert workspace.statistics.assets_generated == 0
    assert workspace.statistics.assets_pending == 0
    assert workspace.prospects == []
    assert workspace.assets == []
    assert workspace.recommendations == []
    assert workspace.job is None
    assert workspace.last_execution is None
    # no deadline, progress 0 -> AT_RISK per _classify_health's no-deadline branch.
    assert workspace.health == PipelineHealth.AT_RISK


async def test_load_for_complete_mission_aggregates_every_domain():
    service, repos = _build_service()
    mission = await repos["mission_repository"].create(
        name="Expansão Goiânia",
        status=MissionStatus.RUNNING,
        priority=MissionPriority.NORMAL,
        progress=50,
        target_city="Goiânia",
        started_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    await repos["mission_metrics_repository"].create(
        mission_id=mission.id,
        companies_found=5,
        companies_qualified=3,
        prospects_created=2,
        meetings=1,
        contracts=0,
        conversion_rate=10.0,
        won_value=1500,
    )
    await repos["mission_event_repository"].create(
        mission_id=mission.id, event="mission_created", occurred_at=datetime.now(timezone.utc)
    )

    company_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    prospect_a = await repos["prospect_repository"].create(
        mission_id=mission.id,
        company_id=company_id,
        campaign_id=campaign_id,
        priority=ProspectPriority.NORMAL,
        status=ProspectStatus.OPEN,
        temperature=ProspectTemperature.WARM,
        current_stage=ProspectStage.CONTACT_READY,
    )
    prospect_b = await repos["prospect_repository"].create(
        mission_id=mission.id,
        company_id=uuid.uuid4(),
        campaign_id=campaign_id,
        priority=ProspectPriority.NORMAL,
        status=ProspectStatus.OPEN,
        temperature=ProspectTemperature.COLD,
        current_stage=ProspectStage.NEW,
    )

    template_id = uuid.uuid4()
    repos["outreach_asset_repository"].create(
        prospect_id=prospect_a.id,
        template_id=template_id,
        asset_type=AssetType.EMAIL,
        channel=Channel.EMAIL,
        content="Olá!",
        status=MessageStatus.PENDING_APPROVAL,
        generated_by="copy_agent",
    )
    repos["outreach_asset_repository"].create(
        prospect_id=prospect_b.id,
        template_id=template_id,
        asset_type=AssetType.EMAIL,
        channel=Channel.EMAIL,
        content="Oi!",
        status=MessageStatus.APPROVED,
        generated_by="copy_agent",
    )

    analysis = AnalysisResult(
        profile=CommercialProfile(
            segment=CommercialSegment.CORPORATE, company_size=CompanySize.SMALL
        ),
        strategy_used=CommercialSegment.CORPORATE,
        score=CommercialScore(
            company_score=60,
            potential_score=60,
            urgency_score=60,
            visibility_score=60,
            relationship_score=60,
            conversion_probability=60,
            total_score=60,
        ),
        recommendations=[
            Recommendation(
                title="Priorizar contato",
                description="Empresa com bom encaixe de segmento.",
                priority=Priority.HIGH,
                confidence=80,
                reason="Score total acima de 50.",
            )
        ],
    )
    repos["sales_intelligence_repository"].save(company_id, analysis)

    await repos["interaction_repository"].create(
        prospect_id=prospect_a.id,
        type=InteractionType.EMAIL,
        occurred_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    job = repos["job_repository"].create(
        job_type="create_prospecting_mission", mission_id=mission.id
    )
    repos["job_repository"].update(
        job, status=JobStatus.RUNNING, started_at=datetime.now(timezone.utc)
    )
    repos["job_repository"].update(
        job, status=JobStatus.FINISHED, finished_at=datetime.now(timezone.utc)
    )

    workspace = await service.load(MissionWorkspaceQuery(mission_id=mission.id))

    assert workspace is not None
    assert workspace.statistics.companies_found == 5
    assert workspace.statistics.qualified == 3
    assert workspace.statistics.assets_generated == 2
    assert workspace.statistics.assets_pending == 1
    assert workspace.statistics.estimated_revenue == 1500
    assert len(workspace.prospects) == 2
    assert len(workspace.assets) == 2
    assert len(workspace.recommendations) == 1
    assert workspace.recommendations[0].title == "Priorizar contato"
    assert len(workspace.timeline) == 1
    assert workspace.timeline[0].event == "mission_created"
    assert workspace.job is not None
    assert workspace.job.status == JobStatus.FINISHED
    assert workspace.last_execution is not None


async def test_load_for_finished_mission_is_healthy_when_progress_is_complete():
    service, repos = _build_service()
    mission = await repos["mission_repository"].create(
        name="Missão Concluída",
        status=MissionStatus.FINISHED,
        priority=MissionPriority.NORMAL,
        progress=100,
        deadline=date.today() - timedelta(days=1),
        finished_at=datetime.now(timezone.utc),
    )
    await repos["mission_metrics_repository"].create(mission_id=mission.id)

    workspace = await service.load(MissionWorkspaceQuery(mission_id=mission.id))

    assert workspace is not None
    assert workspace.mission.status == MissionStatus.FINISHED
    assert workspace.health == PipelineHealth.HEALTHY
