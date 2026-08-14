import uuid
from datetime import datetime, timezone
from typing import Any

from app.crm.exceptions.crm_exceptions import (
    CompanyNotFoundError,
    OpportunityNotFoundError,
    PipelineNotFoundError,
    StageNotFoundError,
)
from app.crm.models.crm_activity import CRMActivity
from app.crm.models.crm_company import CRMCompany
from app.crm.models.crm_contact import CRMContact
from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.models.crm_stage import CRMStage
from app.crm.models.enums import ActivityType, OpportunityStatus
from app.crm.repositories.activity_repository import ActivityRepository
from app.crm.repositories.company_repository import CompanyRepository
from app.crm.repositories.contact_repository import ContactRepository
from app.crm.repositories.opportunity_repository import OpportunityRepository
from app.crm.repositories.pipeline_repository import PipelineRepository
from app.crm.schemas.crm_dashboard import CRMDashboard


class CRMEngine:
    """Represents the full commercial relationship — companies, contacts,
    opportunities, activities, and the pipeline they move through. It runs no AI,
    sends no messages, runs no Workflows, and never imports ProspectEngine or
    anything outside app.crm: it only models the CRM.
    """

    def __init__(
        self,
        company_repository: CompanyRepository,
        contact_repository: ContactRepository,
        opportunity_repository: OpportunityRepository,
        activity_repository: ActivityRepository,
        pipeline_repository: PipelineRepository,
    ) -> None:
        self.company_repository = company_repository
        self.contact_repository = contact_repository
        self.opportunity_repository = opportunity_repository
        self.activity_repository = activity_repository
        self.pipeline_repository = pipeline_repository

    def create_company(
        self,
        name: str,
        *,
        segment: str | None = None,
        city: str | None = None,
        state: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CRMCompany:
        company = CRMCompany(
            name=name, segment=segment, city=city, state=state, metadata=metadata or {}
        )
        return self.company_repository.save_company(company)

    def create_contact(
        self,
        company_id: uuid.UUID,
        name: str,
        *,
        role: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> CRMContact:
        if self.company_repository.get_company(company_id) is None:
            raise CompanyNotFoundError(company_id)

        contact = CRMContact(company_id=company_id, name=name, role=role, email=email, phone=phone)
        return self.contact_repository.save_contact(contact)

    def create_opportunity(
        self,
        company_id: uuid.UUID,
        title: str,
        *,
        pipeline_id: uuid.UUID,
        contact_id: uuid.UUID | None = None,
    ) -> CRMOpportunity:
        if self.company_repository.get_company(company_id) is None:
            raise CompanyNotFoundError(company_id)

        first_stage = self._first_stage(pipeline_id)
        opportunity = CRMOpportunity(
            company_id=company_id,
            contact_id=contact_id,
            title=title,
            pipeline_id=pipeline_id,
            stage_id=first_stage.id,
            status=first_stage.outcome,
        )
        return self.opportunity_repository.save_opportunity(opportunity)

    def move_stage(self, opportunity_id: uuid.UUID, stage_id: uuid.UUID) -> CRMOpportunity:
        opportunity = self.opportunity_repository.get_opportunity(opportunity_id)
        if opportunity is None:
            raise OpportunityNotFoundError(opportunity_id)

        stage = self._get_stage(opportunity.pipeline_id, stage_id)
        opportunity.stage_id = stage.id
        opportunity.status = stage.outcome
        opportunity.updated_at = datetime.now(timezone.utc)
        return self.opportunity_repository.save_opportunity(opportunity)

    def register_activity(
        self, opportunity_id: uuid.UUID, activity_type: ActivityType, *, notes: str | None = None
    ) -> CRMActivity:
        if self.opportunity_repository.get_opportunity(opportunity_id) is None:
            raise OpportunityNotFoundError(opportunity_id)

        activity = CRMActivity(opportunity_id=opportunity_id, type=activity_type, notes=notes)
        return self.activity_repository.save_activity(activity)

    def list_pipeline(self, pipeline_id: uuid.UUID) -> list[CRMStage]:
        pipeline = self.pipeline_repository.get_pipeline(pipeline_id)
        if pipeline is None:
            raise PipelineNotFoundError(pipeline_id)
        return sorted(pipeline.stages, key=lambda stage: stage.order)

    def get_dashboard(self) -> CRMDashboard:
        companies = self.company_repository.list_companies()
        contacts = self.contact_repository.list_contacts()
        opportunities = self.opportunity_repository.list_opportunities()

        by_stage: dict[str, int] = {}
        for opportunity in opportunities:
            stage_name = self._stage_name(opportunity.pipeline_id, opportunity.stage_id)
            by_stage[stage_name] = by_stage.get(stage_name, 0) + 1

        won = sum(1 for o in opportunities if o.status == OpportunityStatus.WON)
        lost = sum(1 for o in opportunities if o.status == OpportunityStatus.LOST)
        closed = won + lost
        conversion_rate = (won / closed) if closed else 0.0

        return CRMDashboard(
            total_companies=len(companies),
            total_contacts=len(contacts),
            total_opportunities=len(opportunities),
            by_stage=by_stage,
            won=won,
            lost=lost,
            conversion_rate=conversion_rate,
        )

    def _first_stage(self, pipeline_id: uuid.UUID) -> CRMStage:
        pipeline = self.pipeline_repository.get_pipeline(pipeline_id)
        if pipeline is None or not pipeline.stages:
            raise PipelineNotFoundError(pipeline_id)
        return min(pipeline.stages, key=lambda stage: stage.order)

    def _get_stage(self, pipeline_id: uuid.UUID, stage_id: uuid.UUID) -> CRMStage:
        pipeline = self.pipeline_repository.get_pipeline(pipeline_id)
        if pipeline is None:
            raise PipelineNotFoundError(pipeline_id)
        stage = next((s for s in pipeline.stages if s.id == stage_id), None)
        if stage is None:
            raise StageNotFoundError(stage_id)
        return stage

    def _stage_name(self, pipeline_id: uuid.UUID, stage_id: uuid.UUID) -> str:
        try:
            return self._get_stage(pipeline_id, stage_id).name
        except (PipelineNotFoundError, StageNotFoundError):
            return "Unknown"
