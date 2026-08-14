from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from app.shared.registry.registry import Registry


@dataclass(frozen=True)
class _Item:
    label: str


def _registry(*items: _Item) -> Registry[_Item]:
    return Registry(items=tuple(items), key=lambda item: item.label)


def test_registro_adds_the_given_item():
    item = _Item("alpha")
    registry = _registry()

    updated = registry.register(item)

    assert updated.list() == [item]
    assert registry.list() == []


def test_register_many_adds_every_given_item_in_order():
    item_a = _Item("alpha")
    item_b = _Item("beta")
    registry = _registry()

    updated = registry.register_many([item_a, item_b])

    assert updated.list() == [item_a, item_b]


def test_find_existente_returns_the_matching_item():
    item = _Item("alpha")
    registry = _registry(item)

    assert registry.find("alpha") is item


def test_find_inexistente_returns_none():
    registry = _registry(_Item("alpha"))

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = _registry(_Item("alpha"))

    assert registry.exists("alpha") is True
    assert registry.exists("does_not_exist") is False


def test_list_preserva_ordem():
    registry = _registry(_Item("alpha"), _Item("beta"), _Item("gamma"))

    assert [item.label for item in registry.list()] == ["alpha", "beta", "gamma"]


def test_register_never_mutates_the_previous_registry():
    original = _registry()

    updated = original.register(_Item("alpha"))

    assert original.list() == []
    assert updated.list() != []
    assert original is not updated


def test_registry_e_generico_nao_conhece_dominios():
    import inspect

    from app.shared.registry import registry as registry_module

    source = inspect.getsource(registry_module)
    assert "Command" not in source
    assert "Query" not in source
    assert "Module" not in source
    assert "app.application" not in source
    assert "app.platform" not in source


def test_imutabilidade_rejects_attribute_assignment():
    registry = _registry(_Item("alpha"))

    with pytest.raises(ValidationError):
        registry.items = ()
