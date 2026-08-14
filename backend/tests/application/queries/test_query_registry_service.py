import inspect

import pytest
from pydantic import ValidationError

from app.application.catalog.application_catalog import ApplicationCatalog
from app.application.catalog.application_catalog_service_factory import (
    build_default_application_catalog_service,
)
from app.application.catalog.application_operation import ApplicationOperation
from app.application.queries import query_registry_service
from app.application.queries.application_query import ApplicationQuery
from app.application.queries.query_registry import QueryRegistry
from app.application.queries.query_registry_service import QueryRegistryService
from app.application.queries.query_registry_service_factory import (
    build_default_query_registry_service,
)


class _FakeApplicationCatalogService:
    def __init__(self, operations: list[ApplicationOperation]) -> None:
        self._operations = operations

    def build_catalog(self) -> ApplicationCatalog:
        return ApplicationCatalog(operations=tuple(self._operations))


def _operation(
    *, name: str = "executive_dashboard", description: str = "Build.", enabled: bool = True
) -> ApplicationOperation:
    return ApplicationOperation(
        name=name,
        display_name=description,
        description=description,
        category="executive",
        enabled=enabled,
    )


def test_build_registry_converts_every_operation_from_the_catalog_service():
    service = QueryRegistryService(_FakeApplicationCatalogService([_operation()]))

    registry = service.build_registry()

    assert isinstance(registry, QueryRegistry)
    assert len(registry.queries) == 1
    query = registry.queries[0]
    assert query.name == "executive_dashboard"
    assert query.description == "Build."
    assert query.enabled is True
    assert query.operation_name == "executive_dashboard"


def test_build_registry_reflects_whatever_the_catalog_service_returns():
    operations = [
        _operation(name="alpha", description="Alpha.", enabled=True),
        _operation(name="beta", description="Beta.", enabled=False),
    ]
    service = QueryRegistryService(_FakeApplicationCatalogService(operations))

    registry = service.build_registry()

    assert [q.name for q in registry.queries] == ["alpha", "beta"]
    assert registry.queries[1].enabled is False


def test_find_existente_returns_the_matching_query():
    service = QueryRegistryService(_FakeApplicationCatalogService([_operation()]))

    query = service.find("executive_dashboard")

    assert isinstance(query, ApplicationQuery)
    assert query.name == "executive_dashboard"


def test_find_inexistente_returns_none():
    service = QueryRegistryService(_FakeApplicationCatalogService([_operation()]))

    assert service.find("does_not_exist") is None


def test_exists_true_when_query_is_registered():
    service = QueryRegistryService(_FakeApplicationCatalogService([_operation()]))

    assert service.exists("executive_dashboard") is True


def test_exists_false_when_query_is_not_registered():
    service = QueryRegistryService(_FakeApplicationCatalogService([_operation()]))

    assert service.exists("does_not_exist") is False


def test_list_queries_returns_exactly_the_registrys_own_tuple():
    service = QueryRegistryService(_FakeApplicationCatalogService([_operation()]))

    listed = service.list_queries()
    registry = service.build_registry()

    assert listed == registry.queries


def test_injecao_uses_exactly_the_service_provided():
    fake = _FakeApplicationCatalogService([])

    service = QueryRegistryService(fake)

    assert service._application_catalog_service is fake


def test_imutabilidade_rejects_attribute_assignment():
    service = QueryRegistryService(_FakeApplicationCatalogService([_operation()]))
    registry = service.build_registry()

    with pytest.raises(ValidationError):
        registry.queries = ()

    with pytest.raises(ValidationError):
        registry.queries[0].enabled = False


def test_build_default_query_registry_service_returns_a_usable_service():
    service = build_default_query_registry_service()

    assert isinstance(service, QueryRegistryService)
    registry = service.build_registry()
    assert isinstance(registry, QueryRegistry)
    assert service.exists("executive_dashboard") is True


def test_build_default_uses_the_real_application_catalog_service():
    real_catalog_service = build_default_application_catalog_service()
    service = QueryRegistryService(real_catalog_service)

    registry = service.build_registry()

    assert len(registry.queries) == len(real_catalog_service.build_catalog().operations)


def test_nenhum_import_de_crm():
    source = inspect.getsource(query_registry_service)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(query_registry_service)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(query_registry_service)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(query_registry_service)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(query_registry_service)
    assert "app.contracts" not in source
