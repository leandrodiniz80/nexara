import time
from typing import Any

from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.copy_task import CopyTask
from app.application.tasks.executors.task_executor import TaskExecutor
from app.application.tasks.qualification_task import QualificationTask
from app.application.tasks.research_task import ResearchTask
from app.application.use_cases.mission.create_prospecting_mission_request import (
    CreateProspectingMissionRequest,
)
from app.application.use_cases.mission.create_prospecting_mission_response import (
    CreateProspectingMissionResponse,
)
from app.application.use_cases.mission.mission_execution_summary import MissionExecutionSummary
from app.jobs.engine.job_engine import JobEngine
from app.models.prospecting.company import Company
from app.models.prospecting.enums import CampaignChannel, ProspectOrigin
from app.models.prospecting.prospect import Prospect
from app.outreach.models.enums import MessageStatus
from app.repositories.prospecting.campaign_repository import CampaignRepository
from app.repositories.prospecting.company_repository import CompanyRepository
from app.research.pipeline.strategy_kind import StrategyKind
from app.research.services.cnpj import normalize_cnpj
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.enums import CommercialSegment, CompanySize
from app.schemas.mission.mission import MissionRead
from app.schemas.prospecting.company import CompanyRead
from app.schemas.prospecting.prospect import ProspectRead
from app.services.mission.mission_engine import MissionEngine
from app.services.prospecting.prospect_engine import ProspectEngine

_SEGMENT_ALIASES: dict[str, CommercialSegment] = {
    "varejo": CommercialSegment.RETAIL,
    "retail": CommercialSegment.RETAIL,
    "saude": CommercialSegment.HEALTHCARE,
    "saúde": CommercialSegment.HEALTHCARE,
    "healthcare": CommercialSegment.HEALTHCARE,
    "imoveis": CommercialSegment.REAL_ESTATE,
    "imóveis": CommercialSegment.REAL_ESTATE,
    "imobiliaria": CommercialSegment.REAL_ESTATE,
    "imobiliária": CommercialSegment.REAL_ESTATE,
    "real_estate": CommercialSegment.REAL_ESTATE,
    "automotivo": CommercialSegment.AUTOMOTIVE,
    "automotive": CommercialSegment.AUTOMOTIVE,
    "educacao": CommercialSegment.EDUCATION,
    "educação": CommercialSegment.EDUCATION,
    "education": CommercialSegment.EDUCATION,
    "pet": CommercialSegment.PET,
    "shopping": CommercialSegment.SHOPPING,
    "franquia": CommercialSegment.FRANCHISE,
    "franchise": CommercialSegment.FRANCHISE,
    "corporativo": CommercialSegment.CORPORATE,
    "corporate": CommercialSegment.CORPORATE,
}


def _map_commercial_segment(segment: str) -> CommercialSegment:
    """Research/Mission's `segment` is a free string (whatever the caller typed);
    Sales Intelligence's CommercialSegment is a closed, 9-value enum. This is a
    best-effort adapter between two vocabularies that happen to share a name, not a
    qualification rule — CORPORATE is the generic fallback when nothing matches,
    same idea as OutreachEngine defaulting an AssetType from a Channel value."""
    return _SEGMENT_ALIASES.get(segment.strip().lower(), CommercialSegment.CORPORATE)


def _map_campaign_channel(value: str) -> CampaignChannel:
    try:
        return CampaignChannel(value)
    except ValueError:
        return CampaignChannel.EMAIL


def _research_variables(request: CreateProspectingMissionRequest) -> dict[str, Any]:
    if request.city:
        return {"strategy": StrategyKind.CITY.value, "query": {"city": request.city}}
    return {"strategy": StrategyKind.SEGMENT.value, "query": {"segment": request.segment}}


def _build_commercial_profile(company: dict[str, Any], segment: str) -> CommercialProfile:
    """ResearchResult carries no firmographic sizing data (no employee count, no
    revenue) — CompanySize.SMALL is a documented, conservative default for "unknown",
    not a scoring decision; the actual scoring rules live entirely in
    SalesIntelligenceEngine's strategies, untouched by this use case."""
    return CommercialProfile(
        segment=_map_commercial_segment(segment),
        company_size=CompanySize.SMALL,
    )


def _extract_cnpj(company: dict[str, Any]) -> str | None:
    """Skips company creation rather than fabricating a CNPJ Research never found —
    inventing a legal registration number would be worse than not creating the
    Prospect at all."""
    raw = company.get("cnpj")
    if not raw:
        return None
    digits = normalize_cnpj(raw)
    return digits if len(digits) == 14 else None


class CreateProspectingMissionUseCase:
    """The platform's first complete business flow: Mission -> Job -> Research ->
    Qualification -> Prospect -> Copy -> Approval -> Summary.

    Every step is a call into an already-existing module (MissionEngine, JobEngine,
    ResearchTask, QualificationTask, ProspectEngine, CopyTask) — this class contains
    no scoring, no prompt text, no approval rule of its own. Its only "logic" is
    sequencing calls, translating between DTOs the existing modules already define,
    and deciding what to do when one step doesn't produce enough to continue (skip
    with a warning, never fabricate missing data).
    """

    def __init__(
        self,
        mission_engine: MissionEngine,
        job_engine: JobEngine,
        company_repository: CompanyRepository,
        campaign_repository: CampaignRepository,
        prospect_engine: ProspectEngine,
        task_executor: TaskExecutor,
        research_task: ResearchTask,
        qualification_task: QualificationTask,
        copy_task: CopyTask,
    ) -> None:
        self.mission_engine = mission_engine
        self.job_engine = job_engine
        self.company_repository = company_repository
        self.campaign_repository = campaign_repository
        self.prospect_engine = prospect_engine
        self.task_executor = task_executor
        self.research_task = research_task
        self.qualification_task = qualification_task
        self.copy_task = copy_task

    async def execute(
        self, request: CreateProspectingMissionRequest
    ) -> CreateProspectingMissionResponse:
        start = time.perf_counter()
        warnings: list[str] = []
        errors: list[str] = []
        companies_found = 0
        qualified_companies: list[dict[str, Any]] = []
        created: list[tuple[Prospect, Company]] = []
        assets: list[dict[str, Any]] = []

        # 1. Criar Mission.
        mission = await self.mission_engine.create(
            name=request.mission_name,
            objective=f"Prospectar empresas do segmento {request.segment}",
            target_segment=request.segment,
            target_city=request.city,
            target_state=request.state,
            owner_id=request.requested_by,
            created_by=request.requested_by,
        )

        # 2. Criar Job.
        job = self.job_engine.create(
            job_type="create_prospecting_mission",
            requested_by=request.requested_by,
            mission_id=mission.id,
        )
        job = self.job_engine.start(job)

        try:
            campaign = await self.campaign_repository.create(
                mission_id=mission.id,
                name=f"{request.mission_name} — Prospecção",
                channel=_map_campaign_channel(request.channel or request.asset_type),
                owner_id=request.requested_by,
                created_by=request.requested_by,
                updated_by=request.requested_by,
            )

            # 3. Executar ResearchTask.
            job = self.job_engine.update_progress(job, progress=10, current_step="research")
            research_context = TaskContext(
                mission_id=mission.id,
                job_id=job.id,
                requested_by=request.requested_by,
                variables=_research_variables(request),
            )
            research_result = await self.task_executor.run(self.research_task, research_context)
            errors.extend(research_result.errors)
            warnings.extend(research_result.warnings)

            # 4. Receber empresas encontradas.
            companies: list[dict[str, Any]] = []
            if research_result.success and research_result.output:
                pipeline_result = research_result.output.get("result")
                if pipeline_result:
                    companies = pipeline_result["companies"]
            companies_found = len(companies)

            # 5. Executar QualificationTask para cada empresa.
            job = self.job_engine.update_progress(job, progress=40, current_step="qualification")
            for company in companies:
                profile = _build_commercial_profile(company, request.segment)
                qualification_context = TaskContext(
                    mission_id=mission.id,
                    job_id=job.id,
                    requested_by=request.requested_by,
                    variables={"profile": profile},
                )
                qualification_result = await self.task_executor.run(
                    self.qualification_task, qualification_context
                )
                if not qualification_result.success:
                    warnings.append(
                        f"Qualificação falhou para '{company['company_name']}': "
                        + "; ".join(qualification_result.errors)
                    )
                    continue

                # 6. Aplicar score mínimo configurável.
                assert qualification_result.output is not None
                score = qualification_result.output["score"]["total_score"]
                if score >= request.minimum_score:
                    qualified_companies.append(company)

            # 7. Criar Prospects elegíveis.
            job = self.job_engine.update_progress(
                job, progress=60, current_step="prospect_creation"
            )
            for company in qualified_companies:
                cnpj = _extract_cnpj(company)
                if cnpj is None:
                    warnings.append(
                        f"'{company['company_name']}' sem CNPJ válido — Prospect não criado."
                    )
                    continue

                company_row = await self.company_repository.create(
                    legal_name=company["company_name"],
                    trade_name=company.get("trade_name"),
                    cnpj=cnpj,
                    segment=request.segment,
                    website=company.get("website"),
                    instagram=company.get("instagram"),
                    linkedin=company.get("linkedin"),
                    city=company.get("city"),
                    state=company.get("state"),
                    created_by=request.requested_by,
                    updated_by=request.requested_by,
                )
                prospect = await self.prospect_engine.create_prospect(
                    company_id=company_row.id,
                    campaign_id=campaign.id,
                    origin=ProspectOrigin.OTHER,
                    created_by=request.requested_by,
                )
                created.append((prospect, company_row))

            # 8. Executar CopyTask. 9. Gerar OutreachAsset.
            # 10. Enviar automaticamente para ApprovalService (feito dentro do
            # próprio CopyTask — ver Sprint 11 — não repetido aqui).
            job = self.job_engine.update_progress(
                job, progress=80, current_step="copy_generation"
            )
            for prospect, company_row in created:
                copy_context = TaskContext(
                    prospect_id=prospect.id,
                    mission_id=mission.id,
                    job_id=job.id,
                    company_id=company_row.id,
                    requested_by=request.requested_by,
                    variables={
                        "company": CompanyRead.model_validate(company_row),
                        "asset_type": request.asset_type,
                        "channel": request.channel,
                        "tone": request.tone,
                        "objective": mission.objective,
                    },
                )
                copy_result = await self.task_executor.run(self.copy_task, copy_context)
                if not copy_result.success:
                    warnings.append(
                        f"Geração de copy falhou para prospect {prospect.id}: "
                        + "; ".join(copy_result.errors)
                    )
                    continue
                assert copy_result.output is not None
                assets.append(copy_result.output)

            job = self.job_engine.finish(
                job,
                output={
                    "companies_found": companies_found,
                    "qualified": len(qualified_companies),
                    "prospects_created": len(created),
                    "assets_generated": len(assets),
                },
            )
        except Exception as exc:  # the use case must never raise past this boundary
            errors.append(str(exc))
            job = self.job_engine.fail(job, error_message=str(exc))

        assets_pending_approval = sum(
            1 for asset in assets if asset.get("status") == MessageStatus.PENDING_APPROVAL.value
        )

        summary = MissionExecutionSummary(
            mission=MissionRead.model_validate(mission),
            job=job,
            companies_found=companies_found,
            qualified=len(qualified_companies),
            prospects_created=len(created),
            assets_generated=len(assets),
            assets_pending_approval=assets_pending_approval,
            execution_time=time.perf_counter() - start,
            warnings=warnings,
            errors=errors,
        )
        return CreateProspectingMissionResponse(
            summary=summary,
            prospects=[ProspectRead.model_validate(prospect) for prospect, _ in created],
            assets=assets,
        )
