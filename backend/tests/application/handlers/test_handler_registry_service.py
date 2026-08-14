import inspect
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.handlers import handler_registry_service
from app.application.handlers.command_handler import CommandHandler
from app.application.handlers.handler_registry import HandlerRegistry
from app.application.handlers.handler_registry_service import HandlerRegistryService
from app.application.handlers.handler_registry_service_factory import (
    build_default_handler_registry_service,
)


class _DummyHandler(CommandHandler):
    def command_name(self) -> str:
        return "dummy_command"

    def handle(self, payload: Any) -> Any:
        return payload


def test_registry_vazio_holds_no_handlers():
    service = HandlerRegistryService(())

    registry = service.build_registry()

    assert isinstance(registry, HandlerRegistry)
    assert registry.handlers == ()


def test_find_inexistente_returns_none():
    service = HandlerRegistryService(())

    assert service.find("does_not_exist") is None


def test_exists_falso_when_no_handler_is_registered():
    service = HandlerRegistryService(())

    assert service.exists("does_not_exist") is False


def test_list_vazio_returns_an_empty_tuple():
    service = HandlerRegistryService(())

    assert service.list_handlers() == ()


def test_command_handler_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        CommandHandler()  # type: ignore[abstract]


def test_injecao_stores_and_finds_the_handlers_provided():
    handler = _DummyHandler()
    service = HandlerRegistryService((handler,))

    assert service.list_handlers() == (handler,)
    assert service.find("dummy_command") is handler
    assert service.exists("dummy_command") is True

    registry = service.build_registry()
    assert registry.handlers == (handler,)


def test_imutabilidade_rejects_attribute_assignment():
    service = HandlerRegistryService(())
    registry = service.build_registry()

    with pytest.raises(ValidationError):
        registry.handlers = ()


def test_build_default_handler_registry_service_registers_the_executive_dashboard_handler():
    service = build_default_handler_registry_service()

    assert isinstance(service, HandlerRegistryService)
    assert service.exists("executive_dashboard") is True
    registry = service.build_registry()
    assert len(registry.handlers) == 1
    assert registry.handlers[0].command_name() == "executive_dashboard"


def test_nenhum_import_de_crm():
    source = inspect.getsource(handler_registry_service)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(handler_registry_service)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(handler_registry_service)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(handler_registry_service)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(handler_registry_service)
    assert "app.contracts" not in source
