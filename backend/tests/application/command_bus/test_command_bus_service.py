import inspect
import time
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.bus.bus_execution_service import BusExecutionService
from app.application.command_bus import command_bus
from app.application.command_bus.command_bus import CommandBus
from app.application.command_bus.command_bus_service import CommandBusService
from app.application.command_bus.command_bus_service_factory import (
    build_default_command_bus_service,
)
from app.application.command_bus.command_request import CommandRequest
from app.application.command_bus.command_result import CommandResult
from app.application.commands.application_command import ApplicationCommand
from app.application.handlers.command_handler import CommandHandler
from app.application.handlers.handler_registry_service import HandlerRegistryService

_COMMAND = ApplicationCommand(
    name="executive_dashboard",
    description="Build executive commercial dashboard.",
    enabled=True,
    operation_name="executive_dashboard",
)


class _FakeCommandRegistryService:
    def __init__(self, commands: dict[str, ApplicationCommand]) -> None:
        self._commands = commands

    def exists(self, name: str) -> bool:
        return name in self._commands

    def find(self, name: str) -> ApplicationCommand | None:
        return self._commands.get(name)


class _DummyHandler(CommandHandler):
    def __init__(self, name: str = "executive_dashboard", response: Any = None) -> None:
        self._name = name
        self.response = response if response is not None else {"ok": True}
        self.calls = 0
        self.received_payload: Any = None

    def command_name(self) -> str:
        return self._name

    def handle(self, payload: Any) -> Any:
        self.calls += 1
        self.received_payload = payload
        return self.response


def _bus(
    *, commands: dict[str, ApplicationCommand], handlers: tuple[CommandHandler, ...]
) -> CommandBus:
    return CommandBus(
        command_registry_service=_FakeCommandRegistryService(commands),
        handler_registry_service=HandlerRegistryService(handlers),
        bus_execution_service=BusExecutionService(),
    )


def test_command_inexistente_returns_a_failure_result():
    bus = _bus(commands={}, handlers=())
    request = CommandRequest(command_name="unknown_command", payload={"x": 1})

    result = bus.execute(request)

    assert result.success is False
    assert result.command_name == "unknown_command"
    assert result.payload is None
    assert result.reason == "Command not found."


def test_registry_vazio_de_handlers_returns_handler_not_registered():
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=())
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    result = bus.execute(request)

    assert result.success is False
    assert result.command_name == "executive_dashboard"
    assert result.payload is None
    assert result.reason == "Handler not registered."


def test_handler_inexistente_for_a_registered_command_returns_handler_not_registered():
    other_handler = _DummyHandler(name="some_other_command")
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=(other_handler,))
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    result = bus.execute(request)

    assert result.success is False
    assert result.reason == "Handler not registered."
    assert other_handler.calls == 0


def test_handler_encontrado_delegates_and_returns_success():
    handler = _DummyHandler(response={"score": 90})
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=(handler,))
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    result = bus.execute(request)

    assert isinstance(result, CommandResult)
    assert result.success is True
    assert result.command_name == "executive_dashboard"
    assert result.payload == {"score": 90}
    assert result.reason is None


def test_delegacao_correta_forwards_the_exact_payload_to_the_handler():
    handler = _DummyHandler()
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=(handler,))
    payload = {"dashboard": "x", "report": "y", "kpis": ["z"]}
    request = CommandRequest(command_name="executive_dashboard", payload=payload)

    bus.execute(request)

    assert handler.calls == 1
    assert handler.received_payload == payload


def test_execution_time_is_a_non_negative_float():
    handler = _DummyHandler()
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=(handler,))
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    result = bus.execute(request)

    assert isinstance(result.execution_time, float)
    assert result.execution_time >= 0.0


def test_injecao_uses_exactly_the_collaborators_provided():
    registry_service = _FakeCommandRegistryService({})
    handler_registry_service = HandlerRegistryService(())
    bus_execution_service = BusExecutionService()

    bus = CommandBus(
        command_registry_service=registry_service,
        handler_registry_service=handler_registry_service,
        bus_execution_service=bus_execution_service,
    )

    assert bus.command_registry_service is registry_service
    assert bus.handler_registry_service is handler_registry_service
    assert bus.bus_execution_service is bus_execution_service


def test_command_bus_service_delegacao_returns_exactly_the_bus_result():
    handler = _DummyHandler(response={"score": 90})
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=(handler,))
    service = CommandBusService(bus)
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    result = service.execute(request)

    assert isinstance(result, CommandResult)
    assert result.success is True
    assert handler.calls == 1


def test_build_default_command_bus_service_has_no_handlers_registered_yet():
    service = build_default_command_bus_service()
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    assert isinstance(service, CommandBusService)
    result = service.execute(request)
    assert result.success is False
    assert result.reason == "Handler not registered."


def test_imutabilidade_rejects_attribute_assignment():
    handler = _DummyHandler()
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=(handler,))
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})
    result = bus.execute(request)

    with pytest.raises(ValidationError):
        bus.handler_registry_service = HandlerRegistryService(())

    with pytest.raises(ValidationError):
        request.command_name = "altered"

    with pytest.raises(ValidationError):
        result.success = False


def test_nenhuma_referencia_a_public_use_case_service():
    source = inspect.getsource(command_bus)
    assert "app.application.public" not in source
    assert "PublicUseCaseService" not in _class_body_only(source)


def _class_body_only(source: str) -> str:
    docstring_end = source.index('"""', source.index('"""') + 3) + 3
    return source[docstring_end:]


def test_nenhum_import_de_crm():
    source = inspect.getsource(command_bus)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(command_bus)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(command_bus)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(command_bus)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(command_bus)
    assert "app.contracts" not in source


def test_nenhum_import_de_platform():
    source = inspect.getsource(command_bus)
    assert "app.platform" not in source


def test_tempo_medido_reflects_the_handlers_actual_duration():
    class _SlowHandler(_DummyHandler):
        def handle(self, payload: Any) -> Any:
            time.sleep(0.01)
            return super().handle(payload)

    handler = _SlowHandler()
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=(handler,))
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    result = bus.execute(request)

    assert result.execution_time > 0.0


def test_handler_chamado_exatamente_uma_vez():
    handler = _DummyHandler()
    bus = _bus(commands={"executive_dashboard": _COMMAND}, handlers=(handler,))
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    bus.execute(request)

    assert handler.calls == 1


class _SpyBusExecutionService(BusExecutionService):
    def __init__(self) -> None:
        self.start_calls: list[str] = []
        self.finish_calls = 0

    def start(self, name: str):
        self.start_calls.append(name)
        return super().start(name)

    def finish(self, start, **kwargs):
        self.finish_calls += 1
        return super().finish(start, **kwargs)


def test_command_bus_usa_bus_execution_service():
    spy = _SpyBusExecutionService()
    handler = _DummyHandler()
    bus = CommandBus(
        command_registry_service=_FakeCommandRegistryService({"executive_dashboard": _COMMAND}),
        handler_registry_service=HandlerRegistryService((handler,)),
        bus_execution_service=spy,
    )
    request = CommandRequest(command_name="executive_dashboard", payload={"x": 1})

    bus.execute(request)

    assert spy.start_calls == ["executive_dashboard"]
    assert spy.finish_calls == 1


def test_nenhuma_dependencia_entre_command_bus_e_query_bus():
    source = inspect.getsource(command_bus)
    assert "app.application.query_bus" not in source
