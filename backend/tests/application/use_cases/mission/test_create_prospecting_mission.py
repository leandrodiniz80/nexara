import uuid

from app.ai.services.ai_orchestrator_factory import build_default_orchestrator
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
from app.jobs.services.job_engine_factory import build_default_job_engine
from app.outreach.models.enums import MessageStatus
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine
from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.pipeline.factory import build_default_lead_discovery_pipeline
from app.research.providers.base.research_provider import ResearchProvider
from app.research.schemas.company_search_query import CompanySearchQuery
from app.research.schemas.contact_lead import ContactLead
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
from tests.mission.fakes import (
    FakeMissionEventRepository,
    FakeMissionMetricsRepository,
    FakeMissionRepository,
)


class _TwoCompanyProvider(ResearchProvider):
    """A real ResearchProvider implementation (not a hand-rolled agent/pipeline fake)
    — the sanctioned way to control what a real LeadDiscoveryPipeline finds, same as
    swapping MockProvider for GoogleMapsProvider would be in production. Returns one
    company with a CNPJ and one without, so a single test run exercises both the
    "Prospect created" and "skipped for missing CNPJ" paths.
    """

    source = ResearchSource.MOCK

    async def search(self, query: CompanySearchQuery) -> list[ResearchResult]:
        return [
            ResearchResult(
                company_name="Agência XYZ",
                trade_name="Agência XYZ",
                cnpj="11222333000181",
                city=query.city or "Goiânia",
                state="GO",
                category=query.segment or "Publicidade",
                source=ResearchSource.MOCK,
            ),
            ResearchResult(
                company_name="Empresa Sem CNPJ",
                trade_name="Empresa Sem CNPJ",
                cnpj=None,
                city=query.city or "Goiânia",
                state="GO",
                category=query.segment or "Publicidade",
                source=ResearchSource.MOCK,
            ),
        ]

    async def get_company(self, identifier: str) -> ResearchResult | None:
        return None

    async def search_contacts(self, company: ResearchResult) -> list[ContactLead]:
        return []

    async def health_check(self) -> bool:
        return True


def _build_use_case() -> CreateProspectingMissionUseCase:
    mission_repo = FakeMissionRepository()
    metrics_repo = FakeMissionMetricsRepository()
    event_repo = FakeMissionEventRepository()
    prospect_repo = FakeProspectRepository()
    campaign_repo = FakeCampaignRepository()
    company_repo = FakeCompanyRepository()

    mission_engine = MissionEngine(
        mission_repo, metrics_repo, prospect_repo, MissionTimeline(event_repo)
    )
    prospect_engine = ProspectEngine(prospect_repo, FakeInteractionRepository(), campaign_repo)

    lead_discovery_pipeline = build_default_lead_discovery_pipeline(
        providers={ResearchSource.MOCK: _TwoCompanyProvider()}
    )

    task_executor = TaskExecutor()
    research_task = ResearchTask(lead_discovery_pipeline)
    qualification_task = QualificationTask(build_default_sales_intelligence_engine())
    copy_task = CopyTask(build_default_orchestrator(), build_default_outreach_engine())

    return CreateProspectingMissionUseCase(
        mission_engine=mission_engine,
        job_engine=build_default_job_engine(),
        company_repository=company_repo,
        campaign_repository=campaign_repo,
        prospect_engine=prospect_engine,
        task_executor=task_executor,
        research_task=research_task,
        qualification_task=qualification_task,
        copy_task=copy_task,
    )


def _request(**overrides) -> CreateProspectingMissionRequest:
    defaults = dict(
        mission_name="Expansão Goiânia",
        segment="Publicidade",
        city="Goiânia",
        state="GO",
        minimum_score=0,
        asset_type="email",
        tone="consultivo",
        requested_by=uuid.uuid4(),
    )
    defaults.update(overrides)
    return CreateProspectingMissionRequest(**defaults)


async def test_full_flow_creates_mission_job_prospect_and_pending_asset():
    use_case = _build_use_case()

    response = await use_case.execute(_request())
    summary = response.summary

    assert summary.companies_found == 2
    assert summary.qualified == 2
    # only "Agência XYZ" has a CNPJ — "Empresa Sem CNPJ" is skipped, not fabricated.
    assert summary.prospects_created == 1
    assert summary.assets_generated == 1
    assert summary.assets_pending_approval == 1
    assert any("CNPJ" in warning for warning in summary.warnings)
    assert summary.errors == []

    assert len(response.prospects) == 1
    assert len(response.assets) == 1
    assert response.assets[0]["status"] == MessageStatus.PENDING_APPROVAL.value


async def test_mission_and_job_are_created_and_linked():
    use_case = _build_use_case()

    response = await use_case.execute(_request())
    summary = response.summary

    assert summary.mission.name == "Expansão Goiânia"
    assert summary.mission.target_segment == "Publicidade"
    assert summary.job.job_type == "create_prospecting_mission"
    assert summary.job.mission_id == summary.mission.id
    assert summary.job.status.value == "finished"


async def test_high_minimum_score_qualifies_fewer_companies():
    use_case = _build_use_case()

    lenient = await use_case.execute(_request(minimum_score=0))
    strict = await use_case.execute(_request(minimum_score=100))

    assert strict.summary.qualified <= lenient.summary.qualified
    assert strict.summary.prospects_created <= lenient.summary.prospects_created


async def test_generated_asset_is_actually_addressed_to_the_created_prospect():
    use_case = _build_use_case()

    response = await use_case.execute(_request())

    prospect_id = str(response.prospects[0].id)
    assert response.assets[0]["prospect_id"] == prospect_id


async def test_execution_time_is_recorded():
    use_case = _build_use_case()

    response = await use_case.execute(_request())

    assert response.summary.execution_time >= 0
