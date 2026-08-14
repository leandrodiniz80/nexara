import uuid
from datetime import datetime, timedelta, timezone

from app.crm.models.crm_activity import CRMActivity
from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.models.enums import ActivityType
from app.crm.services.action_planning_service import ActionPlanningService
from app.crm.services.action_planning_service_factory import build_default_action_planning_service
from app.crm.services.next_action_result import NextActionResult

_NOW = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _opportunity(*, updated_at: datetime | None = None) -> CRMOpportunity:
    return CRMOpportunity(
        company_id=uuid.uuid4(),
        title="Outdoor Digital",
        pipeline_id=uuid.uuid4(),
        stage_id=uuid.uuid4(),
        updated_at=updated_at or _NOW,
    )


def _next_action_result(
    *, action: str | None, success: bool = True, warnings=None, errors=None
) -> NextActionResult:
    return NextActionResult(
        success=success,
        recommended_action=action,
        reason="Opportunity is at some stage.",
        warnings=warnings or [],
        errors=errors or [],
        execution_time=0.001,
    )


def _activity(days_ago: int, activity_type: ActivityType = ActivityType.EMAIL) -> CRMActivity:
    return CRMActivity(
        opportunity_id=uuid.uuid4(),
        type=activity_type,
        created_at=_NOW - timedelta(days=days_ago),
    )


def test_primeiro_contato_is_planned_for_today_high_priority_15_minutes():
    service = ActionPlanningService()
    result = service.plan(
        _opportunity(),
        _next_action_result(action="Realizar primeiro contato"),
        now=_NOW,
    )

    assert result.success is True
    assert result.recommended_date == _NOW.date()
    assert result.recommended_time_window == "Hoje"
    assert result.recommended_priority == "ALTA"
    assert result.estimated_duration == 15


def test_agendar_reuniao_is_planned_within_two_days_high_priority_30_minutes():
    service = ActionPlanningService()
    result = service.plan(
        _opportunity(), _next_action_result(action="Agendar reunião"), now=_NOW
    )

    assert result.success is True
    assert result.recommended_date == _NOW.date() + timedelta(days=2)
    assert result.recommended_time_window == "Até 2 dias"
    assert result.recommended_priority == "ALTA"
    assert result.estimated_duration == 30


def test_enviar_proposta_is_planned_for_the_same_day_medium_priority_20_minutes():
    service = ActionPlanningService()
    result = service.plan(_opportunity(), _next_action_result(action="Enviar proposta"), now=_NOW)

    assert result.success is True
    assert result.recommended_date == _NOW.date()
    assert result.recommended_time_window == "Mesmo dia"
    assert result.recommended_priority == "MÉDIA"
    assert result.estimated_duration == 20


def test_executar_follow_up_is_planned_3_days_after_the_most_recent_activity():
    service = ActionPlanningService()
    activities = [_activity(days_ago=5), _activity(days_ago=1), _activity(days_ago=3)]

    result = service.plan(
        _opportunity(),
        _next_action_result(action="Executar follow-up"),
        activities=activities,
        now=_NOW,
    )

    assert result.success is True
    assert result.recommended_date == (_NOW - timedelta(days=1)).date() + timedelta(days=3)
    assert result.recommended_time_window == "3 dias após proposta"
    assert result.recommended_priority == "ALTA"
    assert result.estimated_duration == 10
    assert result.warnings == []


def test_aguardar_resposta_is_planned_for_7_days_low_priority_5_minutes():
    service = ActionPlanningService()
    result = service.plan(_opportunity(), _next_action_result(action="Aguardar resposta"), now=_NOW)

    assert result.success is True
    assert result.recommended_date == _NOW.date() + timedelta(days=7)
    assert result.recommended_time_window == "7 dias"
    assert result.recommended_priority == "BAIXA"
    assert result.estimated_duration == 5


def test_oportunidade_ganha_recommends_no_action():
    service = ActionPlanningService()
    result = service.plan(_opportunity(), _next_action_result(action="Nenhuma ação"), now=_NOW)

    assert result.success is True
    assert result.recommended_action == "Nenhuma ação"
    assert result.recommended_date is None
    assert result.recommended_time_window is None
    assert result.estimated_duration is None


def test_oportunidade_perdida_recommends_no_action():
    service = ActionPlanningService()
    result = service.plan(_opportunity(), _next_action_result(action="Nenhuma ação"), now=_NOW)

    assert result.success is True
    assert result.recommended_action == "Nenhuma ação"
    assert result.recommended_date is None


def test_empty_history_falls_back_to_the_opportunitys_last_update_with_a_warning():
    updated_at = _NOW - timedelta(days=2)
    service = ActionPlanningService()

    result = service.plan(
        _opportunity(updated_at=updated_at),
        _next_action_result(action="Executar follow-up"),
        activities=[],
        now=_NOW,
    )

    assert result.success is True
    assert result.recommended_date == updated_at.date() + timedelta(days=3)
    assert any("No activity history found" in warning for warning in result.warnings)


def test_multiple_activities_use_the_most_recent_one_as_the_reference():
    older = _activity(days_ago=10)
    most_recent = _activity(days_ago=1)
    middle = _activity(days_ago=5)
    service = ActionPlanningService()

    result = service.plan(
        _opportunity(),
        _next_action_result(action="Executar follow-up"),
        activities=[older, most_recent, middle],
        now=_NOW,
    )

    expected_reference = most_recent.created_at.date()
    assert result.recommended_date == expected_reference + timedelta(days=3)
    assert result.warnings == []


def test_warnings_from_the_next_action_result_are_propagated():
    service = ActionPlanningService()
    result = service.plan(
        _opportunity(),
        _next_action_result(
            action="Realizar primeiro contato",
            warnings=["No activity has been logged for this opportunity yet."],
        ),
        now=_NOW,
    )

    assert result.success is True
    assert "No activity has been logged for this opportunity yet." in result.warnings


def test_a_failed_next_action_result_is_not_planned():
    service = ActionPlanningService()
    result = service.plan(
        _opportunity(),
        _next_action_result(action=None, success=False, errors=["Opportunity not found."]),
        now=_NOW,
    )

    assert result.success is False
    assert result.errors == ["Opportunity not found."]
    assert result.recommended_date is None


def test_an_unknown_recommended_action_fails_gracefully():
    service = ActionPlanningService()
    result = service.plan(
        _opportunity(), _next_action_result(action="Fazer algo inesperado"), now=_NOW
    )

    assert result.success is False
    assert len(result.errors) == 1


def test_build_default_action_planning_service_returns_a_usable_service():
    service = build_default_action_planning_service()

    assert isinstance(service, ActionPlanningService)
    result = service.plan(_opportunity(), _next_action_result(action="Enviar proposta"))
    assert result.success is True
