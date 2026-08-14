import time
import uuid
from typing import Callable

from app.crm.engine.crm_engine import CRMEngine
from app.crm.exceptions.crm_exceptions import OpportunityNotFoundError
from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.models.enums import ActivityType, OpportunityStatus
from app.crm.services.opportunity_lifecycle_result import OpportunityLifecycleResult


class OpportunityLifecycleService:
    """Manages the full lifecycle of an already-created CRMOpportunity —
    moving it between stages, marking it won/lost, scheduling an activity
    against it, closing it, and reopening it. It never creates an
    opportunity: CRMEngine.create_opportunity() remains the only way to do
    that.

    Every operation here is a thin, defensive wrapper around CRMEngine's own
    existing public methods (move_stage(), register_activity(),
    list_pipeline()) and its already-injected repositories — nothing is
    reconstructed, no stage is recalculated, and no rule CRMEngine already
    enforces is duplicated. The only "logic" this class has is picking
    *which* already-defined stage in an opportunity's own pipeline to move it
    to for mark_as_won()/mark_as_lost()/close()/reopen(), by reading each
    CRMStage's own already-set `outcome`/position in the (already sorted)
    list `list_pipeline()` returns — never computing one.
    """

    def __init__(self, crm_engine: CRMEngine) -> None:
        self.crm_engine = crm_engine

    def move_to_stage(
        self, opportunity_id: uuid.UUID, stage_id: uuid.UUID
    ) -> OpportunityLifecycleResult:
        return self._run(lambda: (self.crm_engine.move_stage(opportunity_id, stage_id), []))

    def mark_as_won(self, opportunity_id: uuid.UUID) -> OpportunityLifecycleResult:
        return self._run(lambda: self._move_to_outcome(opportunity_id, OpportunityStatus.WON))

    def mark_as_lost(self, opportunity_id: uuid.UUID) -> OpportunityLifecycleResult:
        return self._run(lambda: self._move_to_outcome(opportunity_id, OpportunityStatus.LOST))

    def close(
        self, opportunity_id: uuid.UUID, *, outcome: OpportunityStatus = OpportunityStatus.WON
    ) -> OpportunityLifecycleResult:
        return self._run(lambda: self._move_to_outcome(opportunity_id, outcome))

    def reopen(self, opportunity_id: uuid.UUID) -> OpportunityLifecycleResult:
        return self._run(lambda: self._move_to_first_stage(opportunity_id))

    def schedule_activity(
        self,
        opportunity_id: uuid.UUID,
        activity_type: ActivityType,
        *,
        notes: str | None = None,
    ) -> OpportunityLifecycleResult:
        start = time.perf_counter()
        try:
            activity = self.crm_engine.register_activity(opportunity_id, activity_type, notes=notes)
            opportunity = self.crm_engine.opportunity_repository.get_opportunity(opportunity_id)
            return OpportunityLifecycleResult(
                success=True,
                opportunity=opportunity,
                activity=activity,
                execution_time=time.perf_counter() - start,
            )
        except Exception as exc:
            return OpportunityLifecycleResult(
                success=False, errors=[str(exc)], execution_time=time.perf_counter() - start
            )

    def _move_to_outcome(
        self, opportunity_id: uuid.UUID, outcome: OpportunityStatus
    ) -> tuple[CRMOpportunity, list[str]]:
        opportunity = self._require_opportunity(opportunity_id)
        warnings: list[str] = []
        if opportunity.status == outcome:
            warnings.append(f"Opportunity is already marked as {outcome.value}.")

        stages = self.crm_engine.list_pipeline(opportunity.pipeline_id)
        stage = next((s for s in stages if s.outcome == outcome), None)
        if stage is None:
            raise LookupError(f"Pipeline has no stage with outcome '{outcome.value}'.")

        moved = self.crm_engine.move_stage(opportunity_id, stage.id)
        return moved, warnings

    def _move_to_first_stage(self, opportunity_id: uuid.UUID) -> tuple[CRMOpportunity, list[str]]:
        opportunity = self._require_opportunity(opportunity_id)
        warnings: list[str] = []

        first_stage = self.crm_engine.list_pipeline(opportunity.pipeline_id)[0]
        if opportunity.stage_id == first_stage.id:
            warnings.append("Opportunity is already at the pipeline's first stage.")

        moved = self.crm_engine.move_stage(opportunity_id, first_stage.id)
        return moved, warnings

    def _require_opportunity(self, opportunity_id: uuid.UUID) -> CRMOpportunity:
        opportunity = self.crm_engine.opportunity_repository.get_opportunity(opportunity_id)
        if opportunity is None:
            raise OpportunityNotFoundError(opportunity_id)
        return opportunity

    @staticmethod
    def _run(
        operation: Callable[[], tuple[CRMOpportunity, list[str]]],
    ) -> OpportunityLifecycleResult:
        start = time.perf_counter()
        try:
            opportunity, warnings = operation()
            return OpportunityLifecycleResult(
                success=True,
                opportunity=opportunity,
                warnings=warnings,
                execution_time=time.perf_counter() - start,
            )
        except Exception as exc:
            return OpportunityLifecycleResult(
                success=False, errors=[str(exc)], execution_time=time.perf_counter() - start
            )
