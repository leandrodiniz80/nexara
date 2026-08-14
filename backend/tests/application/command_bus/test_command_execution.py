from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.application.bus.bus_execution import BusExecution
from app.application.command_bus.command_execution import CommandExecution

_STARTED_AT = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
_FINISHED_AT = _STARTED_AT + timedelta(seconds=0.5)


def _bus_execution(**overrides) -> BusExecution:
    fields = dict(
        name="executive_dashboard",
        started_at=_STARTED_AT,
        finished_at=_FINISHED_AT,
        duration=0.5,
        success=True,
        payload={"ok": True},
        reason=None,
    )
    fields.update(overrides)
    return BusExecution(**fields)


def _execution(**overrides) -> CommandExecution:
    return CommandExecution(bus_execution=_bus_execution(**overrides))


def test_campos_preservados_via_bus_execution():
    execution = _execution()

    assert execution.command == "executive_dashboard"
    assert execution.started_at == _STARTED_AT
    assert execution.finished_at == _FINISHED_AT
    assert execution.duration == 0.5
    assert execution.success is True
    assert execution.payload == {"ok": True}
    assert execution.reason is None


def test_started_at_e_finished_at_sao_datetimes():
    execution = _execution()

    assert isinstance(execution.started_at, datetime)
    assert isinstance(execution.finished_at, datetime)


def test_duration_maior_ou_igual_a_zero():
    execution = _execution(duration=0.0)

    assert execution.duration >= 0.0


def test_reason_preservado_em_falha():
    execution = _execution(success=False, payload=None, reason="Command not found.")

    assert execution.success is False
    assert execution.payload is None
    assert execution.reason == "Command not found."


def test_payload_preservado_em_sucesso():
    execution = _execution(payload={"score": 90}, reason=None)

    assert execution.payload == {"score": 90}


def test_e_um_wrapper_sobre_bus_execution():
    bus_execution = _bus_execution()

    execution = CommandExecution(bus_execution=bus_execution)

    assert execution.bus_execution is bus_execution


def test_imutabilidade_rejects_attribute_assignment():
    execution = _execution()

    with pytest.raises(ValidationError):
        execution.bus_execution = _bus_execution()
