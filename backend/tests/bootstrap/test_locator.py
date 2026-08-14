import pytest

from app.bootstrap.container import DependencyContainer, ServiceNotRegisteredError
from app.bootstrap.service_locator import ServiceLocator


class _ServiceA:
    pass


def test_get_delegates_to_the_underlying_container():
    container = DependencyContainer()
    instance = _ServiceA()
    container.register(instance)

    locator = ServiceLocator(container)

    assert locator.get(_ServiceA) is instance


def test_get_for_an_unregistered_type_raises():
    locator = ServiceLocator(DependencyContainer())

    with pytest.raises(ServiceNotRegisteredError):
        locator.get(_ServiceA)


def test_has_delegates_to_the_underlying_container():
    container = DependencyContainer()
    locator = ServiceLocator(container)

    assert locator.has(_ServiceA) is False

    container.register(_ServiceA())

    assert locator.has(_ServiceA) is True


def test_list_types_delegates_to_the_underlying_container():
    container = DependencyContainer()
    container.register(_ServiceA())
    locator = ServiceLocator(container)

    assert locator.list_types() == [_ServiceA]


def test_service_locator_exposes_no_write_method_at_all():
    """"Read-only" here means the capability doesn't exist on this class —
    there is no register()/set()/add() a caller could ever call."""
    locator = ServiceLocator(DependencyContainer())

    for write_method_name in ("register", "set", "add", "bind", "put"):
        assert not hasattr(locator, write_method_name)


def test_service_locator_registering_a_new_service_on_the_container_directly_is_visible():
    """The underlying container can still be mutated by whoever holds it
    (Bootstrap) — the read-only guarantee is specifically about ServiceLocator
    itself, not about the container object ceasing to be mutable by anyone."""
    container = DependencyContainer()
    locator = ServiceLocator(container)
    assert locator.has(_ServiceA) is False

    container.register(_ServiceA())

    assert locator.has(_ServiceA) is True
