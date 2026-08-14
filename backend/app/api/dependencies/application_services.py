from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator.ai_orchestrator import AIOrchestrator
from app.ai.services.ai_orchestrator_factory import build_default_orchestrator
from app.api.dependencies.common import get_db
from app.application.services.mission_application_service import MissionApplicationService
from app.application.services.outreach_application_service import OutreachApplicationService
from app.application.services.prospect_application_service import ProspectApplicationService
from app.application.services.workspace_application_service import WorkspaceApplicationService
from app.application.tasks.copy_task import CopyTask
from app.application.tasks.executors.task_executor import TaskExecutor
from app.application.tasks.qualification_task import QualificationTask
from app.application.tasks.research_task import ResearchTask
from app.application.use_cases.mission.create_prospecting_mission import (
    CreateProspectingMissionUseCase,
)
from app.application.workspaces.mission.mission_workspace_service import MissionWorkspaceService
from app.jobs.engine.job_engine import JobEngine
from app.jobs.services.job_engine_factory import build_default_job_engine
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine
from app.repositories.mission.mission_event_repository import MissionEventRepository
from app.repositories.mission.mission_metrics_repository import MissionMetricsRepository
from app.repositories.mission.mission_repository import MissionRepository
from app.repositories.prospecting.campaign_repository import CampaignRepository
from app.repositories.prospecting.company_repository import CompanyRepository
from app.repositories.prospecting.interaction_repository import InteractionRepository
from app.repositories.prospecting.prospect_repository import ProspectRepository
from app.research.pipeline.factory import build_default_lead_discovery_pipeline
from app.research.pipeline.lead_discovery_pipeline import LeadDiscoveryPipeline
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.sales_intelligence.engine.sales_intelligence_engine import SalesIntelligenceEngine
from app.sales_intelligence.repositories.sales_intelligence_repository import (
    SalesIntelligenceRepository,
)
from app.sales_intelligence.services.sales_intelligence_engine_factory import (
    build_default_sales_intelligence_engine,
)
from app.services.mission.mission_engine import MissionEngine
from app.services.mission.mission_timeline import MissionTimeline
from app.services.prospecting.prospect_engine import ProspectEngine

# --- Process-wide, in-memory collaborators --------------------------------------
# Cached via lru_cache and reached only through Depends() — never a bare module
# global — which is what keeps in-memory state (Outreach templates/assets, Sales
# Intelligence results) consistent across every route and every request while
# still being overridable per-test via app.dependency_overrides, unlike a real
# global would be.


@lru_cache
def get_outreach_engine() -> OutreachEngine:
    return build_default_outreach_engine()


@lru_cache
def get_ai_orchestrator() -> AIOrchestrator:
    return build_default_orchestrator()


@lru_cache
def get_sales_intelligence_engine() -> SalesIntelligenceEngine:
    return build_default_sales_intelligence_engine()


@lru_cache
def get_lead_discovery_pipeline() -> LeadDiscoveryPipeline:
    return build_default_lead_discovery_pipeline()


@lru_cache
def get_job_engine() -> JobEngine:
    return build_default_job_engine()


@lru_cache
def get_research_result_repository() -> ResearchResultRepository:
    return ResearchResultRepository()


@lru_cache
def get_sales_intelligence_repository() -> SalesIntelligenceRepository:
    return SalesIntelligenceRepository()


# --- Per-request, database-backed collaborators ---------------------------------
# One AsyncSession per request (via get_db) flows into all of these — never cached,
# since sharing a session across concurrent requests would be a real bug, not a
# performance shortcut.


def get_mission_engine(session: AsyncSession = Depends(get_db)) -> MissionEngine:
    return MissionEngine(
        MissionRepository(session),
        MissionMetricsRepository(session),
        ProspectRepository(session),
        MissionTimeline(MissionEventRepository(session)),
    )


def get_prospect_engine(session: AsyncSession = Depends(get_db)) -> ProspectEngine:
    return ProspectEngine(
        ProspectRepository(session), InteractionRepository(session), CampaignRepository(session)
    )


def get_create_prospecting_mission_use_case(
    session: AsyncSession = Depends(get_db),
    mission_engine: MissionEngine = Depends(get_mission_engine),
    prospect_engine: ProspectEngine = Depends(get_prospect_engine),
    job_engine: JobEngine = Depends(get_job_engine),
    ai_orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
    outreach_engine: OutreachEngine = Depends(get_outreach_engine),
    lead_discovery_pipeline: LeadDiscoveryPipeline = Depends(get_lead_discovery_pipeline),
    sales_intelligence_engine: SalesIntelligenceEngine = Depends(get_sales_intelligence_engine),
) -> CreateProspectingMissionUseCase:
    return CreateProspectingMissionUseCase(
        mission_engine=mission_engine,
        job_engine=job_engine,
        company_repository=CompanyRepository(session),
        campaign_repository=CampaignRepository(session),
        prospect_engine=prospect_engine,
        task_executor=TaskExecutor(),
        research_task=ResearchTask(lead_discovery_pipeline),
        qualification_task=QualificationTask(sales_intelligence_engine),
        copy_task=CopyTask(ai_orchestrator, outreach_engine),
    )


def get_mission_workspace_service(
    session: AsyncSession = Depends(get_db),
    job_engine: JobEngine = Depends(get_job_engine),
    research_result_repository: ResearchResultRepository = Depends(
        get_research_result_repository
    ),
    sales_intelligence_repository: SalesIntelligenceRepository = Depends(
        get_sales_intelligence_repository
    ),
    outreach_engine: OutreachEngine = Depends(get_outreach_engine),
) -> MissionWorkspaceService:
    return MissionWorkspaceService(
        mission_repository=MissionRepository(session),
        mission_metrics_repository=MissionMetricsRepository(session),
        mission_event_repository=MissionEventRepository(session),
        job_repository=job_engine.repository,
        prospect_repository=ProspectRepository(session),
        research_result_repository=research_result_repository,
        sales_intelligence_repository=sales_intelligence_repository,
        outreach_asset_repository=outreach_engine.asset_repository,
        interaction_repository=InteractionRepository(session),
    )


# --- Application Services (what every route actually depends on) ---------------


def get_mission_application_service(
    use_case: CreateProspectingMissionUseCase = Depends(get_create_prospecting_mission_use_case),
    mission_engine: MissionEngine = Depends(get_mission_engine),
    workspace_service: MissionWorkspaceService = Depends(get_mission_workspace_service),
) -> MissionApplicationService:
    return MissionApplicationService(use_case, mission_engine, workspace_service)


def get_prospect_application_service(
    ai_orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
    outreach_engine: OutreachEngine = Depends(get_outreach_engine),
    sales_intelligence_engine: SalesIntelligenceEngine = Depends(get_sales_intelligence_engine),
) -> ProspectApplicationService:
    return ProspectApplicationService(
        task_executor=TaskExecutor(),
        qualification_task=QualificationTask(sales_intelligence_engine),
        copy_task=CopyTask(ai_orchestrator, outreach_engine),
        outreach_engine=outreach_engine,
    )


def get_workspace_application_service(
    workspace_service: MissionWorkspaceService = Depends(get_mission_workspace_service),
) -> WorkspaceApplicationService:
    return WorkspaceApplicationService(workspace_service)


def get_outreach_application_service(
    outreach_engine: OutreachEngine = Depends(get_outreach_engine),
) -> OutreachApplicationService:
    return OutreachApplicationService(outreach_engine)
