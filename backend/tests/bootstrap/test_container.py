import pytest

from app.bootstrap.container import DependencyContainer, ServiceNotRegisteredError


class _ServiceA:
    pass


class _ServiceB:
    pass


def test_register_and_get_round_trip_by_inferred_type():
    container = DependencyContainer()
    instance = _ServiceA()

    container.register(instance)

    assert container.get(_ServiceA) is instance


def test_get_for_an_unregistered_type_raises():
    container = DependencyContainer()

    with pytest.raises(ServiceNotRegisteredError):
        container.get(_ServiceA)


def test_register_with_an_explicit_as_type():
    container = DependencyContainer()
    instance = _ServiceA()

    container.register(instance, as_type=_ServiceB)

    assert container.get(_ServiceB) is instance
    with pytest.raises(ServiceNotRegisteredError):
        container.get(_ServiceA)


def test_registering_again_for_the_same_type_overwrites():
    container = DependencyContainer()
    first = _ServiceA()
    second = _ServiceA()
    container.register(first)

    container.register(second)

    assert container.get(_ServiceA) is second


def test_has_reflects_registration_state():
    container = DependencyContainer()

    assert container.has(_ServiceA) is False

    container.register(_ServiceA())

    assert container.has(_ServiceA) is True


def test_list_types_returns_every_registered_type():
    container = DependencyContainer()
    container.register(_ServiceA())
    container.register(_ServiceB())

    assert set(container.list_types()) == {_ServiceA, _ServiceB}


def test_list_types_returns_a_copy_not_the_internal_dict_keys_view():
    container = DependencyContainer()
    container.register(_ServiceA())

    snapshot = container.list_types()
    snapshot.append(_ServiceB)

    assert container.list_types() == [_ServiceA]
