import inspect

from app.platform.bootstrap import platform_container
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.bootstrap.platform_kernel_facade import PlatformKernelFacade

_CONTAINER_READ_METHODS = (
    "catalog",
    "catalog_projection",
    "services_projection",
    "service_names_projection",
    "service_map_projection",
    "service_names",
    "service_map",
    "projections",
    "_build_projections",
    "read_models",
    "read_models_v1",
    "read_models_validated",
    "read_models_version",
)

_KERNEL_READ_METHODS = (
    "catalog",
    "catalog_projection",
    "services",
    "service_map",
    "service_names",
    "service_names_projection",
    "projections",
    "read_models",
    "read_models_v1",
)


def test_fluxo_completo_consistente():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.services() == container.services_projection()
    assert facade.service_map() == container.service_map()
    assert facade.service_names() == container.service_names()
    assert facade.catalog() is container.catalog()
    assert facade.read_models() == container.projections()


def test_equivalencia_entre_camadas():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.projections() == container.read_models()
    assert container.read_models_v1() == container.read_models()
    assert container.service_map() == container.projections()["service_map"]
    assert container.service_names() == container.projections()["service_names"]


def test_identidade_global_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    service_map = container.service_map()
    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance

    assert facade.catalog() is container.catalog() is bootstrap.catalog()

    for direct, projected in zip(container.list(), container.services_projection()):
        assert direct is projected


def test_sistema_nao_usa_resolve_ou_registry_em_leitura():
    for method_name in _CONTAINER_READ_METHODS:
        source = inspect.getsource(getattr(PlatformContainer, method_name))
        assert "resolve(" not in source
        assert "registry" not in source

    for method_name in _KERNEL_READ_METHODS:
        source = inspect.getsource(getattr(PlatformKernelFacade, method_name))
        assert "resolve(" not in source
        assert "registry" not in source


def test_sem_duplicacao_de_logica():
    service_map_source = inspect.getsource(PlatformContainer.service_map)
    assert "{" not in service_map_source
    assert "dict(" not in service_map_source

    service_names_source = inspect.getsource(PlatformContainer.service_names)
    assert "tuple(" not in service_names_source

    for method_name in _KERNEL_READ_METHODS:
        source = inspect.getsource(getattr(PlatformKernelFacade, method_name))
        body = source.split("\n", 1)[1]

        assert "dict(" not in source
        assert "tuple(" not in source
        assert "list(" not in source
        assert "set(" not in source
        assert "{" not in body
        assert "[" not in body


def test_projections_unica_agregacao():
    keys = ('"catalog"', '"services"', '"service_names"', '"service_map"')

    build_source = inspect.getsource(PlatformContainer._build_projections)
    for key in keys:
        assert key in build_source

    other_methods = (
        "catalog_projection",
        "services_projection",
        "service_names_projection",
        "service_map_projection",
        "service_names",
        "service_map",
        "projections",
        "read_models",
        "read_models_v1",
    )
    for method_name in other_methods:
        source = inspect.getsource(getattr(PlatformContainer, method_name))
        keys_present = sum(key in source for key in keys)

        assert keys_present < len(keys)


def test_isolamento_de_camadas():
    for method_name in _KERNEL_READ_METHODS:
        source = inspect.getsource(getattr(PlatformKernelFacade, method_name))

        assert ".list(" not in source

        if method_name not in ("catalog", "catalog_projection"):
            assert ".catalog(" not in source

    container_module_source = inspect.getsource(platform_container)
    assert "PlatformKernelFacade" not in container_module_source

    projections_source = inspect.getsource(PlatformContainer.projections)
    assert "service_map(" not in projections_source
    assert "service_names(" not in projections_source
    assert "services_projection(" not in projections_source
