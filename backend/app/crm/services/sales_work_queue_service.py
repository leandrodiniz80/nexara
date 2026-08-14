from datetime import date, datetime, timezone

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.action_plan import ActionPlan
from app.crm.services.sales_work_queue import SalesWorkQueue
from app.crm.services.sales_work_queue_item import SalesWorkQueueItem

_NO_ACTION = "Nenhuma ação"
_PRIORITY_ORDER = {"ALTA": 0, "MÉDIA": 1, "BAIXA": 2}


class SalesWorkQueueService:
    """Turns a collection of individually-planned ActionPlans into a single,
    deterministically-ordered operational queue for a seller — it executes
    nothing, calls no other module (no Automation, no Runtime, no
    Scheduler), and changes no opportunity. ActionPlanningService continues
    to be the only place that decides *when* a single opportunity's next
    action should happen; this class only ever organizes plans that already
    exist.

    Ordering (all deterministic, stable): overdue items first, then ALTA
    before MÉDIA before BAIXA, then the nearest recommended_date, then the
    opportunity's estimated value (read from `opportunity.metadata`, the
    same generic escape hatch every CRM entity already has — CRMOpportunity
    itself carries no dedicated "value" field) when available, descending.
    """

    def build_queue(
        self,
        planned_opportunities: list[tuple[CRMOpportunity, ActionPlan]],
        *,
        now: datetime | None = None,
    ) -> SalesWorkQueue:
        now = now or datetime.now(timezone.utc)
        today = now.date()
        warnings: list[str] = []
        items: list[SalesWorkQueueItem] = []

        for opportunity, plan in planned_opportunities:
            warnings.extend(plan.warnings)

            if not plan.success:
                warnings.append(
                    "Skipped a failed action plan: " + ("; ".join(plan.errors) or "unknown error")
                )
                continue
            if plan.recommended_action is None or plan.recommended_action == _NO_ACTION:
                continue

            items.append(
                SalesWorkQueueItem(
                    opportunity=opportunity,
                    recommended_action=plan.recommended_action,
                    recommended_date=plan.recommended_date,
                    priority=plan.recommended_priority or "BAIXA",
                    estimated_duration=plan.estimated_duration,
                    reason=plan.reason,
                )
            )

        items.sort(key=lambda item: self._sort_key(item, today))

        overdue = sum(1 for item in items if self._is_overdue(item, today))
        today_count = sum(1 for item in items if item.recommended_date == today)
        future_count = sum(
            1
            for item in items
            if item.recommended_date is not None and item.recommended_date > today
        )

        return SalesWorkQueue(
            items=items,
            total_items=len(items),
            high_priority=sum(1 for item in items if item.priority == "ALTA"),
            medium_priority=sum(1 for item in items if item.priority == "MÉDIA"),
            low_priority=sum(1 for item in items if item.priority == "BAIXA"),
            overdue_items=overdue,
            today_items=today_count,
            future_items=future_count,
            generated_at=now,
            warnings=warnings,
        )

    @staticmethod
    def _is_overdue(item: SalesWorkQueueItem, today: date) -> bool:
        return item.recommended_date is not None and item.recommended_date < today

    @classmethod
    def _sort_key(cls, item: SalesWorkQueueItem, today: date):
        is_overdue = cls._is_overdue(item, today)
        priority_rank = _PRIORITY_ORDER.get(item.priority, len(_PRIORITY_ORDER))
        recommended_date = item.recommended_date or date.max
        value = cls._estimated_value(item)
        return (0 if is_overdue else 1, priority_rank, recommended_date, -value)

    @staticmethod
    def _estimated_value(item: SalesWorkQueueItem) -> float:
        value = item.opportunity.metadata.get("estimated_value")
        return float(value) if isinstance(value, (int, float)) else 0.0
