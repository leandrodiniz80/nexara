import inspect

import pytest
from pydantic import ValidationError

from app.application.bus.bus_execution_service import BusExecutionService
from app.application.query_bus import query_bus
from app.application.query_bus.query_bus import QueryBus
from app.application.query_bus.query_bus_service import QueryBusService
from app.application.query_bus.query_bus_service_factory import build_default_query_bus_service
from app.application.query_bus.query_request import QueryRequest
from app.application.query_bus.query_result import QueryResult


class _FakeQueryRegistryService:
    def __init__(self, names: set[str]) -> None:
        self._names = names

    def exists(self, name: str) -> bool:
        return name in self._names


def _bus(*, names: set[str]) -> QueryBus:
    return QueryBus(
        query_registry_service=_FakeQueryRegistryService(names),
        bus_execution_service=BusExecutionService(),
    )


def test_query_inexistente_returns_a_failure_result():
    bus = _bus(names=set())
    request = QueryRequest(query_name="unknown_query")

    result = bus.execute(request)

    assert result.success is False
    assert result.query_name == "unknown_query"
    assert result.payload is None
    assert result.reason == "Query not found."


def test_query_existente_returns_handler_not_registered():
    bus = _bus(names={"executive_dashboard"})
    request = QueryRequest(query_name="executive_dashboard")

    result = bus.execute(request)

    assert result.success is False
    assert result.query_name == "executive_dashboard"
    assert result.reason == "Query handler not registered."


def test_handler_inexistente_never_executes_anything():
    bus = _bus(names={"executive_dashboard"})
    request = QueryRequest(query_name="executive_dashboard", payload={"x": 1})

    result = bus.execute(request)

    assert result.success is False
    assert result.payload is None
    assert result.reason == "Query handler not registered."


def test_injecao_uses_exactly_the_service_provided():
    registry_service = _FakeQueryRegistryService(set())
    bus_execution_service = BusExecutionService()

    bus = QueryBus(
        query_registry_service=registry_service, bus_execution_service=bus_execution_service
    )

    assert bus.query_registry_service is registry_service
    assert bus.bus_execution_service is bus_execution_service


def test_delegacao_returns_exactly_the_bus_result():
    bus = _bus(names={"executive_dashboard"})
    service = QueryBusService(bus)
    request = QueryRequest(query_name="executive_dashboard")

    result = service.execute(request)

    assert isinstance(result, QueryResult)
    assert result.reason == "Query handler not registered."


def test_build_default_query_bus_service_returns_a_usable_service():
    service = build_default_query_bus_service()
    request = QueryRequest(query_name="executive_dashboard")

    assert isinstance(service, QueryBusService)
    result = service.execute(request)
    assert isinstance(result, QueryResult)
    assert result.success is False
    assert result.reason == "Query handler not registered."


def test_build_default_query_bus_service_reports_unknown_queries():
    service = build_default_query_bus_service()
    request = QueryRequest(query_name="does_not_exist")

    result = service.execute(request)

    assert result.reason == "Query not found."


def test_imutabilidade_rejects_attribute_assignment():
    bus = _bus(names={"executive_dashboard"})
    request = QueryRequest(query_name="executive_dashboard")
    result = bus.execute(request)

    with pytest.raises(ValidationError):
        bus.query_registry_service = _FakeQueryRegistryService(set())

    with pytest.raises(ValidationError):
        request.query_name = "altered"

    with pytest.raises(ValidationError):
        result.success = True


def test_execution_time_is_a_non_negative_float():
    bus = _bus(names={"executive_dashboard"})
    request = QueryRequest(query_name="executive_dashboard")

    result = bus.execute(request)

    assert isinstance(result.execution_time, float)
    assert result.execution_time >= 0.0


def test_nenhum_import_de_crm():
    source = inspect.getsource(query_bus)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(query_bus)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(query_bus)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(query_bus)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(query_bus)
    assert "app.contracts" not in source


def test_nenhum_import_de_platform():
    source = inspect.getsource(query_bus)
    assert "app.platform" not in source


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


def test_query_bus_usa_bus_execution_service():
    spy = _SpyBusExecutionService()
    bus = QueryBus(
        query_registry_service=_FakeQueryRegistryService({"executive_dashboard"}),
        bus_execution_service=spy,
    )
    request = QueryRequest(query_name="executive_dashboard")

    bus.execute(request)

    assert spy.start_calls == ["executive_dashboard"]
    assert spy.finish_calls == 1


def test_query_bus_nao_cria_query_execution():
    source = inspect.getsource(query_bus)
    assert "QueryExecution" not in source


def test_nenhuma_dependencia_entre_query_bus_e_command_bus():
    source = inspect.getsource(query_bus)
    assert "app.application.command_bus" not in source
