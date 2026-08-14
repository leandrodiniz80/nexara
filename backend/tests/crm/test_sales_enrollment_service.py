import inspect
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services import sales_enrollment_service
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution import SalesCadenceExecutionStatus
from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService
from app.crm.services.sales_cadence_step import SalesCadenceStep
from app.crm.services.sales_enrollment import SalesEnrollment
from app.crm.services.sales_enrollment_service import SalesEnrollmentService
from app.crm.services.sales_enrollment_service_factory import (
    build_default_sales_enrollment_service,
)
from app.crm.services.sales_playbook import SalesPlaybook

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
]


def _opportunity() -> CRMOpportunity:
    return CRMOpportunity(
        company_id=uuid.uuid4(),
        title="Outdoor Digital",
        pipeline_id=uuid.uuid4(),
        stage_id=uuid.uuid4(),
    )


def _playbook() -> SalesPlaybook:
    return SalesPlaybook(
        name="Cadência Comercial Padrão",
        description="Abordagem comercial padrão.",
        target_segment="Publicidade",
        company_size="Qualquer",
        priority="ALTA",
        cadence_name="Cadência Comercial Padrão",
        estimated_duration=12,
        recommended_channels=["E-mail", "WhatsApp", "Telefone"],
    )


def _cadence() -> SalesCadence:
    return SalesCadence(
        steps=list(_STEPS),
        total_steps=len(_STEPS),
        current_step=_STEPS[0],
        next_step=_STEPS[1],
    )


def test_criacao_do_enrollment_aggregates_all_four_objects():
    service = SalesEnrollmentService(SalesCadenceExecutionService())
    opportunity, playbook, cadence = _opportunity(), _playbook(), _cadence()

    enrollment = service.enroll(opportunity, playbook, cadence, now=_NOW)

    assert isinstance(enrollment, SalesEnrollment)
    assert enrollment.opportunity is opportunity
    assert enrollment.playbook is playbook
    assert enrollment.cadence is cadence


def test_playbook_preservado_keeps_the_exact_instance():
    service = SalesEnrollmentService(SalesCadenceExecutionService())
    playbook = _playbook()

    enrollment = service.enroll(_opportunity(), playbook, _cadence(), now=_NOW)

    assert enrollment.playbook is playbook
    assert enrollment.playbook.cadence_name == "Cadência Comercial Padrão"


def test_cadencia_preservada_keeps_the_exact_instance():
    service = SalesEnrollmentService(SalesCadenceExecutionService())
    cadence = _cadence()

    enrollment = service.enroll(_opportunity(), _playbook(), cadence, now=_NOW)

    assert enrollment.cadence is cadence


def test_execution_criada_automaticamente_starts_the_cadence():
    service = SalesEnrollmentService(SalesCadenceExecutionService())

    enrollment = service.enroll(_opportunity(), _playbook(), _cadence(), now=_NOW)

    assert enrollment.execution is not None
    assert enrollment.execution.status == SalesCadenceExecutionStatus.IN_PROGRESS
    assert enrollment.status == SalesCadenceExecutionStatus.IN_PROGRESS
    assert enrollment.started_at == _NOW


def test_execution_comeca_no_primeiro_passo():
    service = SalesEnrollmentService(SalesCadenceExecutionService())

    enrollment = service.enroll(_opportunity(), _playbook(), _cadence(), now=_NOW)

    assert enrollment.execution.current_step.step_number == 1
    assert enrollment.execution.current_step.action == "Primeiro e-mail"


def test_execution_current_step_is_the_exact_first_cadence_step():
    service = SalesEnrollmentService(SalesCadenceExecutionService())
    cadence = _cadence()

    enrollment = service.enroll(_opportunity(), _playbook(), cadence, now=_NOW)

    assert enrollment.execution.current_step is cadence.steps[0]


def test_metadata_preservado_is_carried_through_unchanged():
    service = SalesEnrollmentService(SalesCadenceExecutionService())
    metadata = {"source": "unit-test", "campaign": "q1"}

    enrollment = service.enroll(
        _opportunity(), _playbook(), _cadence(), now=_NOW, metadata=metadata
    )

    assert enrollment.metadata == metadata


def test_metadata_defaults_to_an_empty_dict_when_not_provided():
    service = SalesEnrollmentService(SalesCadenceExecutionService())

    enrollment = service.enroll(_opportunity(), _playbook(), _cadence(), now=_NOW)

    assert enrollment.metadata == {}


def test_ids_diferentes_for_each_enrollment():
    service = SalesEnrollmentService(SalesCadenceExecutionService())

    first = service.enroll(_opportunity(), _playbook(), _cadence(), now=_NOW)
    second = service.enroll(_opportunity(), _playbook(), _cadence(), now=_NOW)

    assert first.id != second.id


def test_build_default_sales_enrollment_service_returns_a_usable_service():
    service = build_default_sales_enrollment_service()

    assert isinstance(service, SalesEnrollmentService)
    enrollment = service.enroll(_opportunity(), _playbook(), _cadence(), now=_NOW)
    assert enrollment.execution.current_step.step_number == 1


def test_imutabilidade_dos_objetos_agregados_rejects_reassignment():
    service = SalesEnrollmentService(SalesCadenceExecutionService())
    enrollment = service.enroll(_opportunity(), _playbook(), _cadence(), now=_NOW)

    with pytest.raises(ValidationError):
        enrollment.opportunity = _opportunity()

    with pytest.raises(ValidationError):
        enrollment.playbook = _playbook()

    with pytest.raises(ValidationError):
        enrollment.cadence = _cadence()


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_enrollment_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_enrollment_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_enrollment_service)
    assert "CRMEngine" not in source
