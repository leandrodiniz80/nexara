import time
import uuid

from app.crm.engine.crm_engine import CRMEngine
from app.crm.exceptions.crm_exceptions import OpportunityNotFoundError
from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.models.enums import OpportunityStatus
from app.crm.services.next_action_result import NextActionResult

_NO_ACTION = "Nenhuma ação"

_NEXT_ACTION_BY_STAGE: dict[str, tuple[str, str]] = {
    "Lead": ("Realizar primeiro contato", "high"),
    "Contato": ("Agendar reunião", "normal"),
    "Reunião": ("Enviar proposta", "normal"),
    "Proposta": ("Executar follow-up", "normal"),
    "Negociação": ("Aguardar resposta", "low"),
}


class NextActionService:
    """Recommends the next commercial action for an existing CRMOpportunity —
    it never executes anything (OpportunityLifecycleService remains the only
    place that changes an opportunity's state) and never calls AI, an LLM,
    Runtime, or Workflow. Every recommendation comes from a fixed,
    deterministic table mapping the opportunity's *current* stage name (plus
    its current status) to a known next action — the same "reference,
    never recompute" convention OpportunityLifecycleService itself follows
    for stage outcomes.
    """

    def __init__(self, crm_engine: CRMEngine) -> None:
        self.crm_engine = crm_engine

    def recommend_next_action(self, opportunity_id: uuid.UUID) -> NextActionResult:
        start = time.perf_counter()
        try:
            opportunity = self._require_opportunity(opportunity_id)
            stages = self.crm_engine.list_pipeline(opportunity.pipeline_id)
            current_stage = next((s for s in stages if s.id == opportunity.stage_id), None)
            if current_stage is None:
                raise LookupError("Opportunity's current stage was not found in its own pipeline.")

            if opportunity.status in (OpportunityStatus.WON, OpportunityStatus.LOST):
                return NextActionResult(
                    success=True,
                    recommended_action=_NO_ACTION,
                    priority="low",
                    reason=(
                        f"Opportunity is already {opportunity.status.value} — "
                        "no further action is recommended."
                    ),
                    execution_time=time.perf_counter() - start,
                )

            mapping = _NEXT_ACTION_BY_STAGE.get(current_stage.name)
            if mapping is None:
                raise LookupError(
                    f"No recommended action is defined for stage '{current_stage.name}'."
                )
            action, priority = mapping

            warnings: list[str] = []

            next_stage = next((s for s in stages if s.order == current_stage.order + 1), None)
            if next_stage is None:
                warnings.append(f"No next stage found after '{current_stage.name}'.")

            if current_stage.name != "Lead":
                activities = self.crm_engine.activity_repository.list_activities(
                    opportunity_id=opportunity_id
                )
                if not activities:
                    warnings.append("No activity has been logged for this opportunity yet.")

            return NextActionResult(
                success=True,
                recommended_action=action,
                recommended_stage=next_stage.name if next_stage is not None else None,
                priority=priority,
                reason=f"Opportunity is at stage '{current_stage.name}'.",
                warnings=warnings,
                execution_time=time.perf_counter() - start,
            )
        except Exception as exc:
            return NextActionResult(
                success=False, errors=[str(exc)], execution_time=time.perf_counter() - start
            )

    def _require_opportunity(self, opportunity_id: uuid.UUID) -> CRMOpportunity:
        opportunity = self.crm_engine.opportunity_repository.get_opportunity(opportunity_id)
        if opportunity is None:
            raise OpportunityNotFoundError(opportunity_id)
        return opportunity
