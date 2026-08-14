import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.operations.history import operation_history_service as operation_history_service_module
from app.operations.history.operation_history import OperationHistory
from app.operations.history.operation_history_event import OperationHistoryEvent
from app.operations.history.operation_history_service import OperationHistoryService
from app.operations.history.operation_history_service_factory import (
    build_default_operation_history_service,
)
from app.operations.models.operation import Operation

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 3, 10, 12, 5, tzinfo=timezone.utc)
_T2 = datetime(2026, 3, 10, 12, 10, tzinfo=timezone.utc)


def _operation() -> Operation:
    return Operation(name="Sync inventory")


def test_history_criado_holds_a_single_created_event():
    service = OperationHistoryService()
    operation = _operation()

    history = service.create(operation, now=_T0)

    assert isinstance(history, OperationHistory)
    assert history.operation_id == operation.id
    assert len(history.events) == 1


def test_created_registrado():
    service = OperationHistoryService()
    operation = _operation()

    history = service.create(operation, now=_T0)

    event = history.events[0]
    assert event.event_type == "created"
    assert event.message == "Operation created."
    assert event.timestamp == _T0


def test_started_registrado():
    service = OperationHistoryService()
    history = service.create(_operation(), now=_T0)

    updated = service.record_started(history, now=_T1)

    assert len(updated.events) == 2
    assert updated.events[-1].event_type == "started"
    assert updated.events[-1].message == "Operation started."


def test_finished_registrado():
    service = OperationHistoryService()
    history = service.create(_operation(), now=_T0)
    history = service.record_started(history, now=_T1)

    updated = service.record_finished(history, now=_T2)

    assert len(updated.events) == 3
    assert updated.events[-1].event_type == "finished"
    assert updated.events[-1].message == "Operation finished."


def test_failed_registrado():
    service = OperationHistoryService()
    history = service.create(_operation(), now=_T0)
    history = service.record_started(history, now=_T1)

    updated = service.record_failed(history, reason="Timeout while syncing.", now=_T2)

    assert len(updated.events) == 3
    assert updated.events[-1].event_type == "failed"
    assert updated.events[-1].message == "Timeout while syncing."


def test_failed_registrado_uses_a_default_message_when_no_reason_is_given():
    service = OperationHistoryService()
    history = service.create(_operation(), now=_T0)

    updated = service.record_failed(history, now=_T1)

    assert updated.events[-1].message == "Operation failed."


def test_eventos_preservam_ordem():
    service = OperationHistoryService()
    operation = _operation()

    history = service.create(operation, now=_T0)
    history = service.record_started(history, now=_T1)
    history = service.record_finished(history, now=_T2)

    assert [e.event_type for e in history.events] == ["created", "started", "finished"]
    assert [e.timestamp for e in history.events] == [_T0, _T1, _T2]


def test_methods_never_modify_the_previous_history():
    service = OperationHistoryService()
    original = service.create(_operation(), now=_T0)

    updated = service.record_started(original, now=_T1)

    assert len(original.events) == 1
    assert len(updated.events) == 2
    assert original is not updated


def test_objetos_frozen_reject_attribute_assignment():
    service = OperationHistoryService()
    history = service.create(_operation(), now=_T0)

    with pytest.raises(ValidationError):
        history.events = ()

    with pytest.raises(ValidationError):
        history.events[0].message = "Alterado"


def test_build_default_operation_history_service_returns_a_usable_service():
    service = build_default_operation_history_service()

    assert isinstance(service, OperationHistoryService)
    history = service.create(_operation(), now=_T0)
    assert len(history.events) == 1


def test_nenhum_import_de_runtime():
    source = inspect.getsource(operation_history_service_module)
    assert "app.runtime" not in source


def test_nenhum_import_de_crm():
    source = inspect.getsource(operation_history_service_module)
    assert "app.crm" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(operation_history_service_module)
    assert "app.workflows" not in source


def test_nenhum_import_de_application():
    source = inspect.getsource(operation_history_service_module)
    assert "app.application" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(operation_history_service_module)
    assert "app.presentation" not in source
