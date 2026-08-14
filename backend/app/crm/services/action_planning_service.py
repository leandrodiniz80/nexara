import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.crm.models.crm_activity import CRMActivity
from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.action_plan import ActionPlan
from app.crm.services.next_action_result import NextActionResult

_NO_ACTION = "Nenhuma ação"

_PLAN_BY_ACTION: dict[str, dict[str, Any]] = {
    "Realizar primeiro contato": {
        "time_window": "Hoje",
        "priority": "ALTA",
        "duration_minutes": 15,
    },
    "Agendar reunião": {
        "time_window": "Até 2 dias",
        "priority": "ALTA",
        "duration_minutes": 30,
    },
    "Enviar proposta": {
        "time_window": "Mesmo dia",
        "priority": "MÉDIA",
        "duration_minutes": 20,
    },
    "Executar follow-up": {
        "time_window": "3 dias após proposta",
        "priority": "ALTA",
        "duration_minutes": 10,
    },
    "Aguardar resposta": {
        "time_window": "7 dias",
        "priority": "BAIXA",
        "duration_minutes": 5,
    },
}


class ActionPlanningService:
    """Turns a NextActionResult recommendation into a concrete, deterministic
    execution plan — WHEN the recommended action should happen, at what
    priority, and how long it should take. It executes nothing, schedules
    nothing, and calls no other module (no Automation, no Scheduler, no
    Worker, no Runtime, no Workflow, no AI): every date here is *computed*
    from the given inputs and returned, never persisted anywhere.

    NextActionService continues to decide *what* to do; this class only ever
    decides *when* — and has no injected collaborator at all, since it needs
    none: it is a pure calculator over whatever CRMOpportunity/
    NextActionResult/activity history its caller already has.
    """

    def plan(
        self,
        opportunity: CRMOpportunity,
        next_action_result: NextActionResult,
        *,
        activities: list[CRMActivity] | None = None,
        now: datetime | None = None,
    ) -> ActionPlan:
        start = time.perf_counter()
        today = (now or datetime.now(timezone.utc)).date()
        warnings = list(next_action_result.warnings)

        if not next_action_result.success:
            errors = list(next_action_result.errors) or [
                "No next action recommendation available to plan."
            ]
            return ActionPlan(
                success=False,
                errors=errors,
                warnings=warnings,
                execution_time=time.perf_counter() - start,
            )

        action = next_action_result.recommended_action
        if action is None or action == _NO_ACTION:
            return ActionPlan(
                success=True,
                recommended_action=_NO_ACTION,
                reason=next_action_result.reason,
                warnings=warnings,
                execution_time=time.perf_counter() - start,
            )

        spec = _PLAN_BY_ACTION.get(action)
        if spec is None:
            return ActionPlan(
                success=False,
                errors=[f"No action plan is defined for recommended action '{action}'."],
                warnings=warnings,
                execution_time=time.perf_counter() - start,
            )

        recommended_date = self._recommended_date(
            action, opportunity, activities or [], today, warnings
        )

        return ActionPlan(
            success=True,
            recommended_action=action,
            recommended_date=recommended_date,
            recommended_time_window=spec["time_window"],
            recommended_priority=spec["priority"],
            estimated_duration=spec["duration_minutes"],
            reason=f"Plan for opportunity '{opportunity.title}': {action}.",
            warnings=warnings,
            execution_time=time.perf_counter() - start,
        )

    @staticmethod
    def _recommended_date(
        action: str,
        opportunity: CRMOpportunity,
        activities: list[CRMActivity],
        today: date,
        warnings: list[str],
    ) -> date:
        if action == "Agendar reunião":
            return today + timedelta(days=2)
        if action == "Aguardar resposta":
            return today + timedelta(days=7)
        if action == "Executar follow-up":
            if activities:
                reference = max(activity.created_at for activity in activities).date()
            else:
                warnings.append(
                    "No activity history found; using the opportunity's last update as "
                    "the reference date for follow-up."
                )
                reference = opportunity.updated_at.date()
            return reference + timedelta(days=3)
        return today  # "Realizar primeiro contato" / "Enviar proposta"
