import uuid
from typing import ClassVar

from app.application.services.application_service_result import ApplicationServiceResult
from app.application.services.base_application_service import BaseApplicationService
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.copy_task import CopyTask
from app.application.tasks.executors.task_executor import TaskExecutor
from app.application.tasks.qualification_task import QualificationTask
from app.outreach.engine.outreach_engine import OutreachEngine
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.schemas.prospecting.company import CompanyRead


class ProspectApplicationService(BaseApplicationService):
    """Single entry point for everything Prospect-related: qualifying a company and
    generating/approving/rejecting the commercial assets addressed to it. Every
    method here is a thin wrapper — qualify()/generate_asset() run an existing
    ApplicationTask through TaskExecutor; approve_asset()/reject_asset() call
    OutreachEngine directly (an existing domain engine, not a Repository), fetching
    the OutreachAsset through OutreachEngine's own `asset_repository` collaborator —
    the same pattern CopyTask itself already uses.
    """

    service_name: ClassVar[str] = "prospect_application_service"

    def __init__(
        self,
        task_executor: TaskExecutor,
        qualification_task: QualificationTask,
        copy_task: CopyTask,
        outreach_engine: OutreachEngine,
    ) -> None:
        super().__init__()
        self.task_executor = task_executor
        self.qualification_task = qualification_task
        self.copy_task = copy_task
        self.outreach_engine = outreach_engine

    async def qualify(
        self,
        profile: CommercialProfile,
        *,
        mission_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        prospect_id: uuid.UUID | None = None,
        requested_by: uuid.UUID | None = None,
    ) -> ApplicationServiceResult:
        async def _operation():
            context = TaskContext(
                mission_id=mission_id,
                company_id=company_id,
                prospect_id=prospect_id,
                requested_by=requested_by,
                variables={"profile": profile},
            )
            result = await self.task_executor.run(self.qualification_task, context)
            if not result.success:
                raise RuntimeError("; ".join(result.errors))
            return result.output

        return await self._run("qualify", _operation)

    async def generate_asset(
        self,
        *,
        prospect_id: uuid.UUID,
        company: CompanyRead,
        asset_type: str,
        channel: str | None = None,
        tone: str | None = None,
        contact_name: str | None = None,
        objective: str | None = None,
        mission_id: uuid.UUID | None = None,
        requested_by: uuid.UUID | None = None,
    ) -> ApplicationServiceResult:
        async def _operation():
            context = TaskContext(
                prospect_id=prospect_id,
                mission_id=mission_id,
                requested_by=requested_by,
                variables={
                    "company": company,
                    "asset_type": asset_type,
                    "channel": channel,
                    "tone": tone,
                    "contact_name": contact_name,
                    "objective": objective,
                },
            )
            result = await self.task_executor.run(self.copy_task, context)
            if not result.success:
                raise RuntimeError("; ".join(result.errors))
            return result.output

        return await self._run("generate_asset", _operation)

    async def approve_asset(
        self, asset_id: uuid.UUID, *, approved_by: uuid.UUID | None = None
    ) -> ApplicationServiceResult:
        async def _operation():
            asset = self._get_asset(asset_id)
            return self.outreach_engine.approve(asset, approved_by=approved_by)

        return await self._run("approve_asset", _operation)

    async def reject_asset(
        self, asset_id: uuid.UUID, *, reason: str | None = None
    ) -> ApplicationServiceResult:
        async def _operation():
            asset = self._get_asset(asset_id)
            return self.outreach_engine.reject(asset, reason=reason)

        return await self._run("reject_asset", _operation)

    def _get_asset(self, asset_id: uuid.UUID):
        asset = self.outreach_engine.asset_repository.get_by_id(asset_id)
        if asset is None:
            raise LookupError(f"OutreachAsset {asset_id} not found.")
        return asset
