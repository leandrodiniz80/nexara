import uuid
from datetime import date, timedelta

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.action_plan import ActionPlan
from app.crm.services.sales_cadence_service import SalesCadenceService
from app.crm.services.sales_cadence_service_factory import build_default_sales_cadence_service
from app.crm.services.sales_work_queue_item import SalesWorkQueueItem

_TODAY = date(2026, 3, 10)


def _opportunity() -> CRMOpportunity:
    return CRMOpportunity(
        company_id=uuid.uuid4(),
        title="Outdoor Digital",
        pipeline_id=uuid.uuid4(),
        stage_id=uuid.uuid4(),
    )


def _plan(
    *,
    action: str | None = "Realizar primeiro contato",
    date_=_TODAY,
    duration: int | None = 15,
    success: bool = True,
    warnings=None,
    errors=None,
) -> ActionPlan:
    return ActionPlan(
        success=success,
        recommended_action=action,
        recommended_date=date_,
        recommended_time_window="Hoje",
        recommended_priority="ALTA",
        estimated_duration=duration,
        reason=f"Plan for {action}.",
        warnings=warnings or [],
        errors=errors or [],
        execution_time=0.001,
    )


def test_oportunidade_nova_starts_at_step_one():
    service = SalesCadenceService()

    cadence = service.build_cadence(_opportunity(), _plan(action="Realizar primeiro contato"))

    assert cadence.current_step.step_number == 1
    assert cadence.current_step.action == "Primeiro e-mail"
    assert cadence.next_step.step_number == 2
    assert cadence.recommended_finish_date == _TODAY + timedelta(days=12)


def test_oportunidade_em_contato_is_at_step_two():
    service = SalesCadenceService()

    cadence = service.build_cadence(_opportunity(), _plan(action="Agendar reunião"))

    assert cadence.current_step.step_number == 2
    assert cadence.current_step.action == "WhatsApp"
    assert cadence.next_step.step_number == 3
    assert cadence.recommended_finish_date == _TODAY + timedelta(days=10)


def test_oportunidade_em_reuniao_is_at_step_three():
    service = SalesCadenceService()

    cadence = service.build_cadence(_opportunity(), _plan(action="Enviar proposta"))

    assert cadence.current_step.step_number == 3
    assert cadence.current_step.action == "Ligação"
    assert cadence.next_step.step_number == 4
    assert cadence.recommended_finish_date == _TODAY + timedelta(days=7)


def test_oportunidade_em_proposta_is_at_step_four():
    service = SalesCadenceService()

    cadence = service.build_cadence(_opportunity(), _plan(action="Executar follow-up"))

    assert cadence.current_step.step_number == 4
    assert cadence.current_step.action == "Segundo e-mail"
    assert cadence.next_step.step_number == 5
    assert cadence.recommended_finish_date == _TODAY + timedelta(days=4)


def test_oportunidade_ganha_has_no_current_or_next_step():
    service = SalesCadenceService()

    cadence = service.build_cadence(_opportunity(), _plan(action="Nenhuma ação"))

    assert cadence.current_step is None
    assert cadence.next_step is None
    assert cadence.recommended_finish_date is None
    assert cadence.total_steps == 5


def test_oportunidade_perdida_has_no_current_or_next_step():
    service = SalesCadenceService()

    cadence = service.build_cadence(_opportunity(), _plan(action="Nenhuma ação"))

    assert cadence.current_step is None
    assert cadence.next_step is None


def test_fila_vazia_still_builds_a_cadence_from_the_action_plan_alone():
    service = SalesCadenceService()

    cadence = service.build_cadence(
        _opportunity(), _plan(action="Realizar primeiro contato"), queue_item=None
    )

    assert cadence.current_step.step_number == 1
    assert cadence.recommended_finish_date is not None


def test_fila_vazia_and_no_plan_date_still_returns_a_cadence_with_a_warning():
    service = SalesCadenceService()
    plan_without_date = _plan(action="Realizar primeiro contato", date_=None)

    cadence = service.build_cadence(_opportunity(), plan_without_date, queue_item=None)

    assert cadence.current_step is not None
    assert cadence.recommended_finish_date is None
    assert any("recommended_finish_date could not be calculated" in w for w in cadence.warnings)


def test_queue_item_date_is_used_when_the_action_plan_has_none():
    service = SalesCadenceService()
    plan_without_date = _plan(action="Realizar primeiro contato", date_=None)
    queue_item = SalesWorkQueueItem(
        opportunity=_opportunity(),
        recommended_action="Realizar primeiro contato",
        recommended_date=_TODAY,
        priority="ALTA",
        estimated_duration=15,
        reason="From the queue.",
    )

    cadence = service.build_cadence(_opportunity(), plan_without_date, queue_item=queue_item)

    assert cadence.recommended_finish_date == _TODAY + timedelta(days=12)
    assert any("used the queue item's date instead" in w for w in cadence.warnings)


def test_warnings_from_the_action_plan_are_propagated():
    service = SalesCadenceService()
    plan = _plan(warnings=["No activity has been logged for this opportunity yet."])

    cadence = service.build_cadence(_opportunity(), plan)

    assert "No activity has been logged for this opportunity yet." in cadence.warnings


def test_a_failed_action_plan_produces_no_cadence():
    service = SalesCadenceService()
    plan = _plan(success=False, errors=["Opportunity not found."])

    cadence = service.build_cadence(_opportunity(), plan)

    assert cadence.steps == []
    assert cadence.total_steps == 0
    assert cadence.errors == ["Opportunity not found."]


def test_stability_of_the_sequence_across_every_stage():
    service = SalesCadenceService()
    actions = [
        "Realizar primeiro contato",
        "Agendar reunião",
        "Enviar proposta",
        "Executar follow-up",
        "Aguardar resposta",
        "Nenhuma ação",
    ]

    for action in actions:
        cadence = service.build_cadence(_opportunity(), _plan(action=action))
        assert [step.step_number for step in cadence.steps] == [1, 2, 3, 4, 5]
        assert [step.action for step in cadence.steps] == [
            "Primeiro e-mail",
            "WhatsApp",
            "Ligação",
            "Segundo e-mail",
            "Follow-up final",
        ]


def test_estimated_duration_is_passed_through_from_the_action_plan():
    service = SalesCadenceService()

    cadence = service.build_cadence(
        _opportunity(), _plan(action="Enviar proposta", duration=20)
    )

    assert cadence.estimated_duration == 20


def test_build_default_sales_cadence_service_returns_a_usable_service():
    service = build_default_sales_cadence_service()

    assert isinstance(service, SalesCadenceService)
    cadence = service.build_cadence(_opportunity(), _plan())
    assert cadence.current_step.step_number == 1
