"""Tests for plan management (Sprint 265) — kept under this filename
(matching the spec's own "test_plan_manager.py" request) even though
there's no separate `PlanManager` class: plans live entirely in
`PlatformAuth` (`_DEFAULT_PLANS`, `get_organization_plan()`/
`set_organization_plan()`/`get_plan_limits()`), already established
before this sprint. See tenants.py's own module docstring for the full
reasoning against building a second, parallel plan store.

This sprint's own additions: the `domains`/`alerts_per_hour` limit keys
on every plan (previously only `users`/`requests_per_day`/`projects`/
`requests_per_minute` existed), and `rename_organization()`.
"""

from app.platform.auth.platform_auth import PlatformAuth


def test_nova_organizacao_comeca_no_plano_free():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme Inc")

    assert auth.get_organization_plan(org_id) == "free"


def test_set_organization_plan_funciona():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme Inc")

    auth.set_organization_plan(org_id, "pro")

    assert auth.get_organization_plan(org_id) == "pro"


def test_set_organization_plan_rejeita_plano_desconhecido():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme Inc")

    try:
        auth.set_organization_plan(org_id, "not-a-real-plan")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_set_organization_plan_organizacao_inexistente_lanca_lookup_error():
    auth = PlatformAuth()

    try:
        auth.set_organization_plan("does-not-exist", "pro")
        assert False, "expected LookupError"
    except LookupError:
        pass


def test_limites_do_plano_free():
    auth = PlatformAuth()

    limits = auth.get_plan_limits("free")

    assert limits["domains"] == 1
    assert limits["alerts_per_hour"] == 50


def test_limites_do_plano_pro():
    auth = PlatformAuth()

    limits = auth.get_plan_limits("pro")

    assert limits["domains"] == 5
    assert limits["alerts_per_hour"] == 500


def test_limites_do_plano_enterprise_sao_ilimitados():
    """-1, this platform's established "unlimited" sentinel (already used
    by every other enterprise limit, e.g. users/requests_per_day) — not a
    large finite number like 999/9999, which check_limit()'s own -1
    short-circuit wouldn't recognize as "no limit" at all."""
    auth = PlatformAuth()

    limits = auth.get_plan_limits("enterprise")

    assert limits["domains"] == -1
    assert limits["alerts_per_hour"] == -1


def test_get_plan_limits_de_plano_desconhecido_retorna_vazio():
    auth = PlatformAuth()

    assert auth.get_plan_limits("not-a-real-plan") == {}


def test_rename_organization_funciona():
    auth = PlatformAuth()
    org_id = auth.create_organization("Old Name")

    auth.rename_organization(org_id, "New Name")

    assert auth.get_organization(org_id)["name"] == "New Name"


def test_rename_organization_inexistente_lanca_lookup_error():
    auth = PlatformAuth()

    try:
        auth.rename_organization("does-not-exist", "New Name")
        assert False, "expected LookupError"
    except LookupError:
        pass


def test_get_organization_plan_organizacao_inexistente_retorna_none():
    auth = PlatformAuth()

    assert auth.get_organization_plan("does-not-exist") is None
