from datetime import timedelta

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.action_plan import ActionPlan
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_step import SalesCadenceStep
from app.crm.services.sales_work_queue_item import SalesWorkQueueItem

_NO_ACTION = "Nenhuma ação"

_CADENCE_STEPS: list[dict] = [
    {
        "step_number": 1,
        "action": "Primeiro e-mail",
        "recommended_delay": 0,
        "channel": "E-mail",
        "goal": "Iniciar contato e apresentar a oferta.",
    },
    {
        "step_number": 2,
        "action": "WhatsApp",
        "recommended_delay": 2,
        "channel": "WhatsApp",
        "goal": "Reforçar contato por um canal mais direto.",
    },
    {
        "step_number": 3,
        "action": "Ligação",
        "recommended_delay": 5,
        "channel": "Telefone",
        "goal": "Conversar diretamente e esclarecer dúvidas.",
    },
    {
        "step_number": 4,
        "action": "Segundo e-mail",
        "recommended_delay": 8,
        "channel": "E-mail",
        "goal": "Retomar contato e reforçar valor.",
    },
    {
        "step_number": 5,
        "action": "Follow-up final",
        "recommended_delay": 12,
        "channel": "E-mail",
        "goal": "Última tentativa antes de encerrar a cadência.",
    },
]

_STEP_INDEX_BY_ACTION: dict[str, int] = {
    "Realizar primeiro contato": 1,
    "Agendar reunião": 2,
    "Enviar proposta": 3,
    "Executar follow-up": 4,
    "Aguardar resposta": 5,
}


class SalesCadenceService:
    """Transforms a commercial opportunity into the platform's standard,
    5-step prospecting cadence — it never contacts anyone, never calls
    Runtime, Workflow, or Automation, and schedules nothing. `steps` is a
    fixed, deterministic definition (never reordered or recomputed); the
    only per-opportunity work this class does is locating which of those
    five steps the opportunity's *already-recommended* action corresponds
    to, and computing when the cadence would be finished from there.

    SalesWorkQueueService continues to be the only place that prioritizes
    work across many opportunities; this class only ever expands a single
    opportunity's own next action into its place within the standard
    cadence.
    """

    def build_cadence(
        self,
        opportunity: CRMOpportunity,
        action_plan: ActionPlan,
        *,
        queue_item: SalesWorkQueueItem | None = None,
    ) -> SalesCadence:
        warnings = list(action_plan.warnings)
        steps = [SalesCadenceStep(**spec) for spec in _CADENCE_STEPS]

        if not action_plan.success:
            errors = list(action_plan.errors) or [
                "No action plan available to build a cadence from."
            ]
            return SalesCadence(steps=[], total_steps=0, warnings=warnings, errors=errors)

        action = action_plan.recommended_action
        if action is None or action == _NO_ACTION:
            return SalesCadence(steps=steps, total_steps=len(steps), warnings=warnings)

        step_index = _STEP_INDEX_BY_ACTION.get(action)
        if step_index is None:
            return SalesCadence(
                steps=[],
                total_steps=0,
                warnings=warnings,
                errors=[f"No cadence step is defined for recommended action '{action}'."],
            )

        current_step = steps[step_index - 1]
        next_step = steps[step_index] if step_index < len(steps) else None
        finish_date = self._recommended_finish_date(
            action_plan, queue_item, current_step, steps[-1], warnings
        )

        return SalesCadence(
            steps=steps,
            total_steps=len(steps),
            estimated_duration=action_plan.estimated_duration,
            current_step=current_step,
            next_step=next_step,
            recommended_finish_date=finish_date,
            warnings=warnings,
        )

    @staticmethod
    def _recommended_finish_date(
        action_plan: ActionPlan,
        queue_item: SalesWorkQueueItem | None,
        current_step: SalesCadenceStep,
        last_step: SalesCadenceStep,
        warnings: list[str],
    ):
        reference_date = action_plan.recommended_date
        if reference_date is None and queue_item is not None:
            reference_date = queue_item.recommended_date
            warnings.append(
                "ActionPlan had no recommended_date; used the queue item's date instead."
            )
        if reference_date is None:
            warnings.append(
                "No reference date available; recommended_finish_date could not be calculated."
            )
            return None

        remaining_delay = last_step.recommended_delay - current_step.recommended_delay
        return reference_date + timedelta(days=remaining_delay)
