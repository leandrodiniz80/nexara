import inspect

from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.bootstrap.platform_kernel_facade import PlatformKernelFacade

_KERNEL_READ_METHODS = (
    "services",
    "service_map",
    "service_names",
    "catalog",
    "projections",
    "read_models",
    "read_models_v1",
)

_CONTAINER_PROJECTION_METHODS = (
    "catalog",
    "catalog_projection",
    "services_projection",
    "service_names_projection",
    "service_map_projection",
    "service_names",
    "service_map",
    "projections",
)


def test_spec_fluxo_oficial():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.services() == container.services_projection() == container.list()
    assert facade.service_map() == container.service_map() == container.service_map_projection()
    assert (
        facade.service_names()
        == container.service_names()
        == container.service_names_projection()
    )
    assert facade.catalog() is container.catalog()
    assert facade.read_models() == container.projections()


def test_spec_separacao_camadas():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert container.bootstrap is bootstrap
    assert facade.container is container

    for method_name in _KERNEL_READ_METHODS:
        source = inspect.getsource(getattr(PlatformKernelFacade, method_name))
        assert "self.container." in source
        assert source.count("\n") <= 2

    assert container.projections() == container.read_models()


def test_spec_regras_negativas():
    for method_name in _KERNEL_READ_METHODS:
        source = inspect.getsource(getattr(PlatformKernelFacade, method_name))
        assert "if " not in source
        assert "for " not in source

    for method_name in _CONTAINER_PROJECTION_METHODS:
        source = inspect.getsource(getattr(PlatformContainer, method_name))
        assert "resolve(" not in source

    projections_source = inspect.getsource(PlatformContainer.projections)
    assert "self.service_map(" not in projections_source
    assert "self.service_names(" not in projections_source
    assert "self.catalog(" not in projections_source
    assert "self.list(" not in projections_source


def test_spec_fontes_oficiais():
    services_projection_source = inspect.getsource(PlatformContainer.services_projection)
    assert "self.list(" in services_projection_source

    catalog_projection_source = inspect.getsource(PlatformContainer.catalog_projection)
    assert "self.catalog(" in catalog_projection_source

    build_projections_source = inspect.getsource(PlatformContainer._build_projections)
    body = build_projections_source.split("\n", 1)[1]
    assert "self.list(" in body
    assert "self.catalog(" in body


def test_spec_invariantes():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    listed = container.list()
    ordered_names = [descriptor.name for descriptor in listed]

    assert list(container.service_names()) == ordered_names
    assert [descriptor.name for descriptor in container.services_projection()] == ordered_names

    for descriptor in listed:
        assert container.service_map()[descriptor.name] is descriptor.instance

    assert container.read_models_v1() == container.read_models()


def test_spec_aderente_ao_codigo():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert isinstance(container.projections(), dict)
    assert isinstance(container.service_map(), dict)
    assert isinstance(container.service_names(), tuple)
    assert isinstance(container.services_projection(), list)
    assert isinstance(facade.services(), list)
    assert isinstance(facade.service_map(), dict)
    assert isinstance(facade.service_names(), tuple)
    assert facade.catalog() is container.catalog()
    assert set(container.projections().keys()) == {
        "catalog",
        "services",
        "service_names",
        "service_map",
    }
