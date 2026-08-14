import pytest
from pydantic import ValidationError

from app.application.queries.application_query import ApplicationQuery
from app.application.queries.query_registry import QueryRegistry


def _query(name: str = "executive_dashboard") -> ApplicationQuery:
    return ApplicationQuery(
        name=name, description="Build.", enabled=True, operation_name=name
    )


def test_queries_field_preserva_api_publica():
    query = _query()

    registry = QueryRegistry(queries=(query,))

    assert registry.queries == (query,)


def test_queries_default_e_tupla_vazia():
    registry = QueryRegistry()

    assert registry.queries == ()


def test_registro_adds_the_given_query():
    query = _query()
    registry = QueryRegistry()

    updated = registry.register(query)

    assert updated.queries == (query,)
    assert registry.queries == ()


def test_register_many_adds_every_given_query_in_order():
    query_a = _query("alpha")
    query_b = _query("beta")
    registry = QueryRegistry()

    updated = registry.register_many([query_a, query_b])

    assert updated.queries == (query_a, query_b)


def test_find_existente_returns_the_matching_query():
    query = _query()
    registry = QueryRegistry(queries=(query,))

    assert registry.find("executive_dashboard") is query


def test_find_inexistente_returns_none():
    registry = QueryRegistry(queries=(_query(),))

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = QueryRegistry(queries=(_query(),))

    assert registry.exists("executive_dashboard") is True
    assert registry.exists("does_not_exist") is False


def test_list_returns_the_registered_queries_in_order():
    query_a = _query("alpha")
    query_b = _query("beta")
    registry = QueryRegistry(queries=(query_a, query_b))

    assert registry.list() == [query_a, query_b]


def test_imutabilidade_rejects_attribute_assignment():
    registry = QueryRegistry(queries=(_query(),))

    with pytest.raises(ValidationError):
        registry.queries = ()
