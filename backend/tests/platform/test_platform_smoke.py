from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.bootstrap.platform_kernel_facade import PlatformKernelFacade


def _build_facade() -> PlatformKernelFacade:
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    return PlatformKernelFacade(container=container)


def test_smoke_bootstrap_container_facade():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert container is not None
    assert facade is not None


def test_smoke_todos_metodos_executam_sem_erro():
    facade = _build_facade()

    facade.services()
    facade.service_map()
    facade.service_names()
    facade.catalog()
    facade.projections()
    facade.read_models()
    facade.read_models_v1()


def test_smoke_estrutura_dados():
    facade = _build_facade()

    assert isinstance(facade.services(), list)
    assert isinstance(facade.service_map(), dict)
    assert isinstance(facade.service_names(), tuple)
    assert facade.catalog() is not None

    projections = facade.projections()
    assert isinstance(projections, dict)
    assert set(projections.keys()) == {
        "catalog",
        "services",
        "service_names",
        "service_map",
    }


def test_smoke_repeticao_consistente():
    facade = _build_facade()

    assert facade.services() == facade.services()
    assert facade.service_map() == facade.service_map()
    assert facade.service_names() == facade.service_names()
    assert facade.catalog() is facade.catalog()
    assert facade.projections() == facade.projections()
    assert facade.read_models() == facade.read_models()


def test_smoke_uso_combinado():
    facade = _build_facade()

    data = facade.read_models()
    services = facade.services()
    names = facade.service_names()
    mapping = facade.service_map()

    assert isinstance(data, dict)
    assert len(services) == len(names)
    assert set(names) == set(mapping.keys())


def test_smoke_compat_layer():
    facade = _build_facade()

    assert facade.read_models_v1() == facade.read_models()
