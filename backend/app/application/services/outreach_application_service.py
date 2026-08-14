import uuid
from typing import ClassVar

from app.application.services.application_service_result import ApplicationServiceResult
from app.application.services.base_application_service import BaseApplicationService
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.schemas.generation_request import GenerationRequest


class OutreachApplicationService(BaseApplicationService):
    """Single entry point for the asset lifecycle: generate (template-based, no
    AI — see ProspectApplicationService.generate_asset() for the AI-backed path
    through CopyTask), submit for approval, approve, reject. Every method is a thin
    wrapper around OutreachEngine, fetching the OutreachAsset it needs through
    OutreachEngine's own `asset_repository` collaborator (same pattern as
    ProspectApplicationService/CopyTask) rather than an independently-injected
    Repository.
    """

    service_name: ClassVar[str] = "outreach_application_service"

    def __init__(self, outreach_engine: OutreachEngine) -> None:
        super().__init__()
        self.outreach_engine = outreach_engine

    async def generate_asset(self, request: GenerationRequest) -> ApplicationServiceResult:
        async def _operation():
            return self.outreach_engine.generate_message(request)

        return await self._run("generate_asset", _operation)

    async def submit_for_approval(self, asset_id: uuid.UUID) -> ApplicationServiceResult:
        async def _operation():
            asset = self._get_asset(asset_id)
            return self.outreach_engine.submit_for_approval(asset)

        return await self._run("submit_for_approval", _operation)

    async def approve(
        self, asset_id: uuid.UUID, *, approved_by: uuid.UUID | None = None
    ) -> ApplicationServiceResult:
        async def _operation():
            asset = self._get_asset(asset_id)
            return self.outreach_engine.approve(asset, approved_by=approved_by)

        return await self._run("approve", _operation)

    async def reject(
        self, asset_id: uuid.UUID, *, reason: str | None = None
    ) -> ApplicationServiceResult:
        async def _operation():
            asset = self._get_asset(asset_id)
            return self.outreach_engine.reject(asset, reason=reason)

        return await self._run("reject", _operation)

    def _get_asset(self, asset_id: uuid.UUID):
        asset = self.outreach_engine.asset_repository.get_by_id(asset_id)
        if asset is None:
            raise LookupError(f"OutreachAsset {asset_id} not found.")
        return asset
