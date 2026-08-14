"""Tests for PricingExperimentEngine (Sprint 282)."""

from app.platform.billing.pricing_experiments import PricingExperimentEngine


class FakeAuth:
    def list_organizations(self) -> dict:
        return {}


def _find_org_ids_for_variants(engine, count_each: int = 1) -> dict[str, list[str]]:
    """Discovers, at test time, synthetic org_ids that map to each
    variant -- there's no way to hand-pick a SHA-256 preimage, so this
    searches a deterministic sequence of candidate ids instead."""
    found: dict[str, list[str]] = {"control": [], "price_up": [], "price_down": []}
    i = 0

    while not all(len(v) >= count_each for v in found.values()):
        org_id = f"org-{i}"
        variant = engine.assign_variant(org_id)
        if len(found[variant]) < count_each:
            found[variant].append(org_id)
        i += 1

        if i > 100_000:
            raise RuntimeError("could not find org_ids for all variants")

    return found


def test_assign_variant_e_deterministico():
    engine = PricingExperimentEngine(FakeAuth())

    first = engine.assign_variant("org_42")
    second = engine.assign_variant("org_42")

    assert first == second


def test_assign_variant_e_deterministico_entre_instancias_diferentes():
    """Regression guard: must not rely on Python's built-in hash(),
    which is randomized per-process -- a fresh engine instance (as if
    from a new process) must agree with an older one."""
    engine_a = PricingExperimentEngine(FakeAuth())
    engine_b = PricingExperimentEngine(FakeAuth())

    for i in range(20):
        org_id = f"org-{i}"
        assert engine_a.assign_variant(org_id) == engine_b.assign_variant(org_id)


def test_assign_variant_retorna_apenas_valores_validos():
    engine = PricingExperimentEngine(FakeAuth())

    for i in range(50):
        assert engine.assign_variant(f"org-{i}") in ("control", "price_up", "price_down")


def test_distribuicao_cobre_os_tres_grupos():
    """Not a statistical balance test -- just confirms a reasonably
    sized batch of orgs doesn't all land in a single bucket, which would
    indicate a broken hash/modulo."""
    engine = PricingExperimentEngine(FakeAuth())

    variants = {engine.assign_variant(f"org-{i}") for i in range(100)}

    assert variants == {"control", "price_up", "price_down"}


def test_preco_control_e_igual_ao_base():
    engine = PricingExperimentEngine(FakeAuth())
    org_ids = _find_org_ids_for_variants(engine)

    price = engine.get_price_for_org(org_ids["control"][0], 100.0)

    assert price == 100.0


def test_preco_price_up_e_20_por_cento_maior():
    engine = PricingExperimentEngine(FakeAuth())
    org_ids = _find_org_ids_for_variants(engine)

    price = engine.get_price_for_org(org_ids["price_up"][0], 100.0)

    assert price == 120.0


def test_preco_price_down_e_20_por_cento_menor():
    engine = PricingExperimentEngine(FakeAuth())
    org_ids = _find_org_ids_for_variants(engine)

    price = engine.get_price_for_org(org_ids["price_down"][0], 100.0)

    assert price == 80.0


def test_preco_e_consistente_com_a_variante_atribuida():
    engine = PricingExperimentEngine(FakeAuth())
    multipliers = {"control": 1.0, "price_up": 1.2, "price_down": 0.8}

    for i in range(30):
        org_id = f"org-{i}"
        variant = engine.assign_variant(org_id)

        price = engine.get_price_for_org(org_id, 99.0)

        assert price == round(99.0 * multipliers[variant], 2)


def test_preco_arredondado_a_duas_casas():
    engine = PricingExperimentEngine(FakeAuth())
    org_ids = _find_org_ids_for_variants(engine)

    price = engine.get_price_for_org(org_ids["price_up"][0], 33.33)

    assert price == round(33.33 * 1.2, 2)
