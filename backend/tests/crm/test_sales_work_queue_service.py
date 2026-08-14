import uuid
from datetime import datetime, timedelta, timezone

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.action_plan import ActionPlan
from app.crm.services.sales_work_queue_service import SalesWorkQueueService
from app.crm.services.sales_work_queue_service_factory import build_default_sales_work_queue_service

_NOW = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _opportunity(*, title: str = "Outdoor Digital", estimated_value: float | None = None):
    metadata = {"estimated_value": estimated_value} if estimated_value is not None else {}
    return CRMOpportunity(
        company_id=uuid.uuid4(),
        title=title,
        pipeline_id=uuid.uuid4(),
        stage_id=uuid.uuid4(),
        metadata=metadata,
    )


def _plan(
    *,
    action: str = "Realizar primeiro contato",
    date_=None,
    priority: str = "ALTA",
    duration: int = 15,
    success: bool = True,
    warnings=None,
    errors=None,
) -> ActionPlan:
    return ActionPlan(
        success=success,
        recommended_action=action,
        recommended_date=date_ if date_ is not None else _NOW.date(),
        recommended_time_window="Hoje",
        recommended_priority=priority,
        estimated_duration=duration,
        reason=f"Plan for {action}.",
        warnings=warnings or [],
        errors=errors or [],
        execution_time=0.001,
    )


def test_empty_queue():
    service = SalesWorkQueueService()

    queue = service.build_queue([], now=_NOW)

    assert queue.items == []
    assert queue.total_items == 0
    assert queue.overdue_items == 0
    assert queue.today_items == 0
    assert queue.future_items == 0


def test_a_single_opportunity_produces_a_single_item():
    opportunity = _opportunity()
    plan = _plan()
    service = SalesWorkQueueService()

    queue = service.build_queue([(opportunity, plan)], now=_NOW)

    assert queue.total_items == 1
    assert queue.items[0].opportunity is opportunity
    assert queue.items[0].recommended_action == "Realizar primeiro contato"
    assert queue.items[0].priority == "ALTA"
    assert queue.items[0].estimated_duration == 15


def test_multiple_priorities_are_counted_and_high_sorts_first():
    high = (_opportunity(title="A"), _plan(priority="ALTA"))
    medium = (_opportunity(title="B"), _plan(priority="MÉDIA"))
    low = (_opportunity(title="C"), _plan(priority="BAIXA"))
    service = SalesWorkQueueService()

    queue = service.build_queue([low, medium, high], now=_NOW)

    assert queue.high_priority == 1
    assert queue.medium_priority == 1
    assert queue.low_priority == 1
    assert [item.priority for item in queue.items] == ["ALTA", "MÉDIA", "BAIXA"]


def test_overdue_items_sort_before_everything_else():
    overdue_plan = _plan(date_=_NOW.date() - timedelta(days=1), priority="BAIXA")
    overdue = (_opportunity(title="Overdue"), overdue_plan)
    urgent_today = (_opportunity(title="Urgent"), _plan(date_=_NOW.date(), priority="ALTA"))
    service = SalesWorkQueueService()

    queue = service.build_queue([urgent_today, overdue], now=_NOW)

    assert queue.overdue_items == 1
    assert queue.items[0].opportunity.title == "Overdue"
    assert queue.items[1].opportunity.title == "Urgent"


def test_today_items_are_counted():
    item = (_opportunity(), _plan(date_=_NOW.date()))
    service = SalesWorkQueueService()

    queue = service.build_queue([item], now=_NOW)

    assert queue.today_items == 1
    assert queue.overdue_items == 0
    assert queue.future_items == 0


def test_future_items_are_counted():
    item = (_opportunity(), _plan(date_=_NOW.date() + timedelta(days=5)))
    service = SalesWorkQueueService()

    queue = service.build_queue([item], now=_NOW)

    assert queue.future_items == 1
    assert queue.overdue_items == 0
    assert queue.today_items == 0


def test_tie_break_by_nearest_recommended_date():
    later_plan = _plan(date_=_NOW.date() + timedelta(days=5), priority="ALTA")
    sooner_plan = _plan(date_=_NOW.date() + timedelta(days=1), priority="ALTA")
    later = (_opportunity(title="Later"), later_plan)
    sooner = (_opportunity(title="Sooner"), sooner_plan)
    service = SalesWorkQueueService()

    queue = service.build_queue([later, sooner], now=_NOW)

    assert [item.opportunity.title for item in queue.items] == ["Sooner", "Later"]


def test_tie_break_by_estimated_value_descending():
    low_value = (
        _opportunity(title="Low value", estimated_value=1000),
        _plan(date_=_NOW.date(), priority="ALTA"),
    )
    high_value = (
        _opportunity(title="High value", estimated_value=50000),
        _plan(date_=_NOW.date(), priority="ALTA"),
    )
    no_value = (_opportunity(title="No value"), _plan(date_=_NOW.date(), priority="ALTA"))
    service = SalesWorkQueueService()

    queue = service.build_queue([low_value, no_value, high_value], now=_NOW)

    assert [item.opportunity.title for item in queue.items] == [
        "High value",
        "Low value",
        "No value",
    ]


def test_ordering_is_stable_for_fully_tied_items():
    first = (_opportunity(title="First"), _plan(date_=_NOW.date(), priority="ALTA"))
    second = (_opportunity(title="Second"), _plan(date_=_NOW.date(), priority="ALTA"))
    third = (_opportunity(title="Third"), _plan(date_=_NOW.date(), priority="ALTA"))
    service = SalesWorkQueueService()

    queue = service.build_queue([first, second, third], now=_NOW)

    assert [item.opportunity.title for item in queue.items] == ["First", "Second", "Third"]


def test_won_and_lost_opportunities_are_excluded_from_the_queue():
    no_action_plan = _plan(action="Nenhuma ação", date_=None, priority=None, duration=None)
    no_action = (_opportunity(), no_action_plan)
    real_work = (_opportunity(), _plan())
    service = SalesWorkQueueService()

    queue = service.build_queue([no_action, real_work], now=_NOW)

    assert queue.total_items == 1
    assert queue.items[0].recommended_action == "Realizar primeiro contato"


def test_failed_plans_are_excluded_and_reported_as_a_warning():
    failed = (_opportunity(), _plan(success=False, errors=["Opportunity not found."]))
    service = SalesWorkQueueService()

    queue = service.build_queue([failed], now=_NOW)

    assert queue.total_items == 0
    assert any("Skipped a failed action plan" in warning for warning in queue.warnings)


def test_warnings_from_individual_plans_are_propagated():
    opportunity = _opportunity()
    plan = _plan(warnings=["No activity history found; using the opportunity's last update."])
    service = SalesWorkQueueService()

    queue = service.build_queue([(opportunity, plan)], now=_NOW)

    assert "No activity history found; using the opportunity's last update." in queue.warnings


def test_build_default_sales_work_queue_service_returns_a_usable_service():
    service = build_default_sales_work_queue_service()

    assert isinstance(service, SalesWorkQueueService)
    queue = service.build_queue([(_opportunity(), _plan())])
    assert queue.total_items == 1
