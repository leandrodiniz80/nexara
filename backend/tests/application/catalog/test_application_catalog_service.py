import inspect

import pytest
from pydantic import ValidationError

from app.application.catalog import application_catalog_service
from app.application.catalog.application_catalog import ApplicationCatalog
from app.application.catalog.application_catalog_service import ApplicationCatalogService
from app.application.catalog.application_catalog_service_factory import (
    build_default_application_catalog_service,
)
from app.application.catalog.application_operation import ApplicationOperation
from app.application.public.public_use_case import PublicUseCase
from app.application.public.public_use_case_service_factory import (
    build_default_public_use_case_service,
)


class _FakePublicUseCaseService:
    def __init__(self, use_cases: list[PublicUseCase]) -> None:
        self._use_cases = use_cases

    def list_use_cases(self) -> list[PublicUseCase]:
        return list(self._use_cases)


def test_build_catalog_converts_every_use_case_from_the_public_service():
    use_case = PublicUseCase(
        name="executive_dashboard",
        description="Build executive commercial dashboard.",
        enabled=True,
    )
    service = ApplicationCatalogService(_FakePublicUseCaseService([use_case]))

    catalog = service.build_catalog()

    assert isinstance(catalog, ApplicationCatalog)
    assert len(catalog.operations) == 1
    operation = catalog.operations[0]
    assert operation.name == "executive_dashboard"
    assert operation.description == "Build executive commercial dashboard."
    assert operation.display_name == "Build executive commercial dashboard."
    assert operation.category == "executive"
    assert operation.enabled is True


def test_build_catalog_reflects_whatever_the_public_service_returns():
    use_cases = [
        PublicUseCase(name="alpha", description="Alpha use case.", enabled=True),
        PublicUseCase(name="beta", description="Beta use case.", enabled=False),
    ]
    service = ApplicationCatalogService(_FakePublicUseCaseService(use_cases))

    catalog = service.build_catalog()

    assert [op.name for op in catalog.operations] == ["alpha", "beta"]
    assert catalog.operations[1].enabled is False


def test_find_existente_returns_the_matching_operation():
    use_case = PublicUseCase(
        name="executive_dashboard",
        description="Build executive commercial dashboard.",
        enabled=True,
    )
    service = ApplicationCatalogService(_FakePublicUseCaseService([use_case]))

    operation = service.find("executive_dashboard")

    assert isinstance(operation, ApplicationOperation)
    assert operation.name == "executive_dashboard"


def test_find_inexistente_returns_none():
    use_case = PublicUseCase(
        name="executive_dashboard",
        description="Build executive commercial dashboard.",
        enabled=True,
    )
    service = ApplicationCatalogService(_FakePublicUseCaseService([use_case]))

    operation = service.find("does_not_exist")

    assert operation is None


def test_imutabilidade_rejects_attribute_assignment():
    use_case = PublicUseCase(
        name="executive_dashboard",
        description="Build executive commercial dashboard.",
        enabled=True,
    )
    service = ApplicationCatalogService(_FakePublicUseCaseService([use_case]))
    catalog = service.build_catalog()

    with pytest.raises(ValidationError):
        catalog.operations = ()

    with pytest.raises(ValidationError):
        catalog.operations[0].enabled = False


def test_injecao_uses_exactly_the_service_provided():
    fake = _FakePublicUseCaseService([])

    service = ApplicationCatalogService(fake)

    assert service._public_use_case_service is fake


def test_build_default_application_catalog_service_returns_a_usable_service():
    service = build_default_application_catalog_service()

    assert isinstance(service, ApplicationCatalogService)
    catalog = service.build_catalog()
    assert isinstance(catalog, ApplicationCatalog)
    assert service.find("executive_dashboard") is not None


def test_build_default_uses_the_real_public_use_case_service():
    real_public_use_case_service = build_default_public_use_case_service()
    service = ApplicationCatalogService(real_public_use_case_service)

    catalog = service.build_catalog()

    assert len(catalog.operations) == len(real_public_use_case_service.list_use_cases())


def test_nenhum_import_de_crm():
    source = inspect.getsource(application_catalog_service)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(application_catalog_service)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(application_catalog_service)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(application_catalog_service)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(application_catalog_service)
    assert "app.contracts" not in source
