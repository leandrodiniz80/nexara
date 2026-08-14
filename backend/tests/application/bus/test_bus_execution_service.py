import time
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.application.bus.bus_execution import BusExecution
from app.application.bus.bus_execution_service import BusExecutionService, BusExecutionStart
from app.application.bus.bus_execution_service_factory import build_default_bus_execution_service


def test_start_returns_a_start_handle_with_the_given_name():
    service = BusExecutionService()

    start = service.start("executive_dashboard")

    assert isinstance(start, BusExecutionStart)
    assert start.name == "executive_dashboard"
    assert isinstance(start.started_at, datetime)


def test_finish_returns_a_bus_execution():
    service = BusExecutionService()
    start = service.start("executive_dashboard")

    execution = service.finish(start, success=True, payload={"ok": True}, reason=None)

    assert isinstance(execution, BusExecution)
    assert execution.name == "executive_dashboard"
    assert execution.success is True
    assert execution.payload == {"ok": True}
    assert execution.reason is None


def test_finish_preserva_started_at_do_start():
    service = BusExecutionService()
    start = service.start("executive_dashboard")

    execution = service.finish(start, success=True)

    assert execution.started_at == start.started_at


def test_finished_at_e_um_datetime():
    service = BusExecutionService()
    start = service.start("executive_dashboard")

    execution = service.finish(start, success=True)

    assert isinstance(execution.finished_at, datetime)


def test_tempo_medido_reflects_actual_elapsed_time():
    service = BusExecutionService()
    start = service.start("executive_dashboard")
    time.sleep(0.01)

    execution = service.finish(start, success=True)

    assert execution.duration > 0.0


def test_duration_maior_ou_igual_a_zero():
    service = BusExecutionService()
    start = service.start("executive_dashboard")

    execution = service.finish(start, success=True)

    assert execution.duration >= 0.0


def test_reason_preservado_em_falha():
    service = BusExecutionService()
    start = service.start("executive_dashboard")

    execution = service.finish(start, success=False, reason="Command not found.")

    assert execution.success is False
    assert execution.reason == "Command not found."


def test_payload_default_e_none():
    service = BusExecutionService()
    start = service.start("executive_dashboard")

    execution = service.finish(start, success=False)

    assert execution.payload is None
    assert execution.reason is None


def test_injecao_reutiliza_o_mesmo_service_em_multiplas_execucoes():
    service = BusExecutionService()

    first = service.finish(service.start("a"), success=True)
    second = service.finish(service.start("b"), success=False, reason="x")

    assert first.name == "a"
    assert second.name == "b"


def test_build_default_bus_execution_service_returns_a_usable_service():
    service = build_default_bus_execution_service()

    assert isinstance(service, BusExecutionService)
    execution = service.finish(service.start("executive_dashboard"), success=True)
    assert isinstance(execution, BusExecution)


def test_bus_execution_imutabilidade_rejects_attribute_assignment():
    service = BusExecutionService()
    execution = service.finish(service.start("executive_dashboard"), success=True)

    with pytest.raises(ValidationError):
        execution.success = False
