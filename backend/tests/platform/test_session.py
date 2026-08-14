import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.platform.session import execution_session, execution_session_service
from app.platform.session.execution_session import ExecutionSession
from app.platform.session.execution_session_factory import build_default_execution_session_service
from app.platform.session.execution_session_service import ExecutionSessionService

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 3, 10, 12, 5, tzinfo=timezone.utc)


def test_sessao_criada():
    service = ExecutionSessionService()

    session = service.create(request_id="req-1", now=_T0)

    assert isinstance(session, ExecutionSession)
    assert session.started_at == _T0
    assert session.finished_at is None


def test_session_id_preservado_across_finish():
    service = ExecutionSessionService()
    session = service.create(now=_T0)

    finished = service.finish(session, now=_T1)

    assert finished.session_id == session.session_id


def test_request_id_preservado_across_finish():
    service = ExecutionSessionService()
    session = service.create(request_id="req-9", now=_T0)

    finished = service.finish(session, now=_T1)

    assert finished.request_id == "req-9"


def test_finished_at_preenchido():
    service = ExecutionSessionService()
    session = service.create(now=_T0)

    finished = service.finish(session, now=_T1)

    assert finished.finished_at == _T1
    assert finished.started_at == _T0


def test_finish_never_mutates_the_given_session():
    service = ExecutionSessionService()
    original = service.create(now=_T0)

    finished = service.finish(original, now=_T1)

    assert original.finished_at is None
    assert finished.finished_at == _T1
    assert original is not finished


def test_objetos_frozen_rejects_attribute_assignment():
    service = ExecutionSessionService()
    session = service.create(now=_T0)

    with pytest.raises(ValidationError):
        session.finished_at = _T1

    with pytest.raises(ValidationError):
        session.session_id = session.session_id


def test_metadata_preservado():
    service = ExecutionSessionService()
    session = service.create(metadata={"tenant": "acme"}, now=_T0)

    finished = service.finish(session, now=_T1)

    assert finished.metadata == {"tenant": "acme"}


def test_build_default_execution_session_service_returns_a_usable_service():
    service = build_default_execution_session_service()

    assert isinstance(service, ExecutionSessionService)
    session = service.create(now=_T0)
    assert isinstance(session, ExecutionSession)


def test_nenhum_import_de_runtime():
    for module in (execution_session, execution_session_service):
        source = inspect.getsource(module)
        assert "app.runtime" not in source


def test_nenhum_import_de_crm():
    for module in (execution_session, execution_session_service):
        source = inspect.getsource(module)
        assert "app.crm" not in source


def test_nenhum_import_de_workflow():
    for module in (execution_session, execution_session_service):
        source = inspect.getsource(module)
        assert "app.workflows" not in source


def test_nenhum_import_de_application():
    for module in (execution_session, execution_session_service):
        source = inspect.getsource(module)
        assert "app.application" not in source


def test_nenhum_import_de_presentation():
    for module in (execution_session, execution_session_service):
        source = inspect.getsource(module)
        assert "app.presentation" not in source


def test_nenhum_import_de_operations():
    for module in (execution_session, execution_session_service):
        source = inspect.getsource(module)
        assert "app.operations" not in source


def test_nenhum_import_de_decision():
    for module in (execution_session, execution_session_service):
        source = inspect.getsource(module)
        assert "app.decision" not in source


def test_nenhum_import_de_observability():
    for module in (execution_session, execution_session_service):
        source = inspect.getsource(module)
        assert "app.observability" not in source
