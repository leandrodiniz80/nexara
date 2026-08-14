import uuid
from datetime import datetime, timedelta, timezone

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution import SalesCadenceExecutionStatus
from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService
from app.crm.services.sales_cadence_execution_service_factory import (
    build_default_sales_cadence_execution_service,
)
from app.crm.services.sales_cadence_step import SalesCadenceStep

_NOW = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)

_STEPS = [
    SalesCadenceStep(
        step_number=1, action="Primeiro e-mail", recommended_delay=0, channel="E-mail", goal="g1"
    ),
    SalesCadenceStep(
        step_number=2, action="WhatsApp", recommended_delay=2, channel="WhatsApp", goal="g2"
    ),
    SalesCadenceStep(
        step_number=3, action="Ligação", recommended_delay=5, channel="Telefone", goal="g3"
    ),
    SalesCadenceStep(
        step_number=4, action="Segundo e-mail", recommended_delay=8, channel="E-mail", goal="g4"
    ),
    SalesCadenceStep(
        step_number=5, action="Follow-up final", recommended_delay=12, channel="E-mail", goal="g5"
    ),
]


def _opportunity() -> CRMOpportunity:
    return CRMOpportunity(
        company_id=uuid.uuid4(),
        title="Outdoor Digital",
        pipeline_id=uuid.uuid4(),
        stage_id=uuid.uuid4(),
    )


def _cadence(*, warnings=None) -> SalesCadence:
    return SalesCadence(
        steps=list(_STEPS),
        total_steps=len(_STEPS),
        current_step=_STEPS[0],
        next_step=_STEPS[1],
        warnings=warnings or [],
    )


def test_cadencia_iniciada_starts_at_the_first_step_with_zero_progress():
    service = SalesCadenceExecutionService()

    execution = service.start(_cadence(), _opportunity(), now=_NOW)

    assert execution.status == SalesCadenceExecutionStatus.IN_PROGRESS
    assert execution.current_step.step_number == 1
    assert execution.completed_steps == []
    assert [s.step_number for s in execution.remaining_steps] == [2, 3, 4, 5]
    assert execution.progress == 0.0
    assert execution.started_at == _NOW
    assert execution.next_due_date == _NOW.date()


def test_avanco_correto_moves_exactly_one_step():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)

    execution = service.advance(execution, now=_NOW)

    assert execution.current_step.step_number == 2
    assert [s.step_number for s in execution.completed_steps] == [1]
    assert [s.step_number for s in execution.remaining_steps] == [3, 4, 5]
    assert execution.progress == 20.0
    assert execution.next_due_date == _NOW.date() + timedelta(days=2)


def test_rollback_correto_reverses_the_last_advance():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)
    execution = service.advance(execution, now=_NOW)
    execution = service.advance(execution, now=_NOW)

    execution = service.rollback(execution, now=_NOW)

    assert execution.current_step.step_number == 2
    assert [s.step_number for s in execution.completed_steps] == [1]
    assert [s.step_number for s in execution.remaining_steps] == [3, 4, 5]
    assert execution.progress == 20.0


def test_rollback_no_primeiro_passo_never_goes_below_the_first_step():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)

    execution = service.rollback(execution, now=_NOW)

    assert execution.current_step.step_number == 1
    assert execution.completed_steps == []
    assert any("Cannot rollback before the first step" in w for w in execution.warnings)


def test_pause_keeps_position():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)
    execution = service.advance(execution, now=_NOW)

    execution = service.pause(execution, now=_NOW)

    assert execution.status == SalesCadenceExecutionStatus.PAUSED
    assert execution.current_step.step_number == 2
    assert [s.step_number for s in execution.completed_steps] == [1]


def test_resume_continues_exactly_where_it_stopped():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)
    execution = service.advance(execution, now=_NOW)
    execution = service.pause(execution, now=_NOW)

    execution = service.resume(execution, now=_NOW)

    assert execution.status == SalesCadenceExecutionStatus.IN_PROGRESS
    assert execution.current_step.step_number == 2


def test_finish_marks_the_cadence_as_complete():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)

    execution = service.finish(execution, now=_NOW)

    assert execution.status == SalesCadenceExecutionStatus.FINISHED
    assert execution.current_step is None
    assert execution.remaining_steps == []
    assert [s.step_number for s in execution.completed_steps] == [1]
    assert execution.finished_at == _NOW
    assert execution.progress == 100.0


def test_100_percent_concluida_after_advancing_through_every_step():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)

    progresses = [execution.progress]
    for _ in range(5):
        execution = service.advance(execution, now=_NOW)
        progresses.append(execution.progress)

    assert progresses == [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    assert execution.status == SalesCadenceExecutionStatus.FINISHED
    assert execution.current_step is None


def test_advance_after_finished_is_a_no_op_with_a_warning():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)
    execution = service.finish(execution, now=_NOW)

    execution = service.advance(execution, now=_NOW)

    assert execution.status == SalesCadenceExecutionStatus.FINISHED
    assert any("already finished" in w for w in execution.warnings)


def test_cadencia_vazia_finishes_immediately_with_a_warning():
    service = SalesCadenceExecutionService()
    empty_cadence = SalesCadence(steps=[], total_steps=0)

    execution = service.start(empty_cadence, _opportunity(), now=_NOW)

    assert execution.status == SalesCadenceExecutionStatus.FINISHED
    assert execution.current_step is None
    assert execution.progress == 100.0
    assert any("no steps to execute" in w for w in execution.warnings)


def test_warnings_propagados_from_the_cadence_flow_into_the_execution():
    service = SalesCadenceExecutionService()
    cadence = _cadence(warnings=["No activity history found; using the opportunity's last update."])

    execution = service.start(cadence, _opportunity(), now=_NOW)

    assert "No activity history found; using the opportunity's last update." in execution.warnings


def test_imutabilidade_dos_passos_preserves_the_exact_step_instances():
    service = SalesCadenceExecutionService()
    cadence = _cadence()

    execution = service.start(cadence, _opportunity(), now=_NOW)

    assert execution.current_step is cadence.steps[0]
    assert execution.remaining_steps[0] is cadence.steps[1]

    execution = service.advance(execution, now=_NOW)

    assert execution.current_step is cadence.steps[1]
    assert execution.completed_steps[0] is cadence.steps[0]


def test_progress_calculado_corretamente_at_every_stage():
    service = SalesCadenceExecutionService()
    execution = service.start(_cadence(), _opportunity(), now=_NOW)
    assert execution.progress == 0.0

    execution = service.advance(execution, now=_NOW)
    assert execution.progress == 20.0

    execution = service.advance(execution, now=_NOW)
    assert execution.progress == 40.0

    execution = service.advance(execution, now=_NOW)
    assert execution.progress == 60.0

    execution = service.advance(execution, now=_NOW)
    assert execution.progress == 80.0

    execution = service.advance(execution, now=_NOW)
    assert execution.progress == 100.0


def test_build_default_sales_cadence_execution_service_returns_a_usable_service():
    service = build_default_sales_cadence_execution_service()

    assert isinstance(service, SalesCadenceExecutionService)
    execution = service.start(_cadence(), _opportunity())
    assert execution.current_step.step_number == 1
