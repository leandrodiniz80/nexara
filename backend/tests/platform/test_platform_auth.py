import pytest

from app.platform.auth.platform_auth import PlatformAuth
from app.platform.cache.platform_cache import InMemoryCache

_EMAIL = "user@example.com"
_PASSWORD = "correct-horse-battery-staple"


def test_login_sem_usuario_registrado_retorna_none():
    auth = PlatformAuth()

    assert auth.login(_EMAIL, _PASSWORD) is None


def test_register_e_login_retorna_sessao():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)

    assert session is not None
    assert session["email"] == _EMAIL
    assert "token" in session


def test_login_senha_errada_retorna_none():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    assert auth.login(_EMAIL, "wrong-password") is None


def test_exists():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    assert auth.exists(_EMAIL) is True
    assert auth.exists("ghost@example.com") is False


def test_get_session_token_invalido_retorna_none():
    auth = PlatformAuth()

    assert auth.get_session("does-not-exist") is None


def test_is_authenticated():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)

    assert auth.is_authenticated(session["token"]) is True
    assert auth.is_authenticated("bogus-token") is False


def test_logout_invalida_sessao():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)
    token = session["token"]

    auth.logout(token)

    assert auth.is_authenticated(token) is False
    assert auth.get_session(token) is None


def test_senha_nao_e_armazenada_em_texto_puro():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    user = auth._users[_EMAIL]

    assert isinstance(user["salt"], bytes)
    assert isinstance(user["hash"], bytes)
    assert len(user["salt"]) > 0
    assert user["hash"] != _PASSWORD.encode()


def test_dois_usuarios_com_mesma_senha_tem_hashes_diferentes():
    auth = PlatformAuth()
    auth.register_user("a@example.com", _PASSWORD)
    auth.register_user("b@example.com", _PASSWORD)

    hash_a = auth._users["a@example.com"]["hash"]
    hash_b = auth._users["b@example.com"]["hash"]

    assert hash_a != hash_b


def test_sessao_expira_apos_ttl():
    auth = PlatformAuth(session_ttl=-1)
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)

    assert auth.get_session(session["token"]) is None
    assert auth.is_authenticated(session["token"]) is False


def test_sessao_dentro_do_ttl_permanece_valida():
    auth = PlatformAuth(session_ttl=3600)
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)

    assert auth.get_session(session["token"]) is not None
    assert auth.is_authenticated(session["token"]) is True


def test_token_assinado_valido():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)

    assert auth.is_authenticated(session["token"]) is True


def test_token_adulterado_rejeitado():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)
    tampered = session["token"] + "hack"

    assert auth.is_authenticated(tampered) is False


def test_token_nao_expoe_email_em_texto_puro():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)

    assert _EMAIL not in session["token"]


def test_logins_concorrentes_geram_tokens_diferentes():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    session_a = auth.login(_EMAIL, _PASSWORD)
    session_b = auth.login(_EMAIL, _PASSWORD)

    assert session_a["token"] != session_b["token"]
    assert auth.is_authenticated(session_a["token"]) is True
    assert auth.is_authenticated(session_b["token"]) is True


def test_token_com_assinatura_diferente_de_outra_instancia_e_rejeitado():
    auth_a = PlatformAuth()
    auth_b = PlatformAuth()

    auth_a.register_user(_EMAIL, _PASSWORD)
    session = auth_a.login(_EMAIL, _PASSWORD)

    assert auth_b.is_authenticated(session["token"]) is False


def test_token_expira():
    auth = PlatformAuth(session_ttl=-1)

    auth.register_user(_EMAIL, _PASSWORD)
    session = auth.login(_EMAIL, _PASSWORD)

    assert auth.is_authenticated(session["token"]) is False


def test_register_sem_org_cria_organizacao_automaticamente():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    org_id = auth.get_user_organization(_EMAIL)

    assert org_id is not None
    assert auth.get_organization(org_id) is not None


def test_primeiro_usuario_da_org_auto_criada_e_owner():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    user = auth._users[_EMAIL]

    assert user["organization_role"] == "owner"


def test_register_com_org_explicita_usa_org_informada():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.register_user(_EMAIL, _PASSWORD, organization_id=org_id)

    assert auth.get_user_organization(_EMAIL) == org_id


def test_register_com_org_explicita_usa_role_padrao_member():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.register_user(_EMAIL, _PASSWORD, organization_id=org_id)

    user = auth._users[_EMAIL]

    assert user["organization_role"] == "member"


def test_create_organization_retorna_id_unico():
    auth = PlatformAuth()

    org_a = auth.create_organization("A")
    org_b = auth.create_organization("B")

    assert org_a != org_b


def test_get_organization_retorna_dados():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    org = auth.get_organization(org_id)

    assert org["name"] == "Acme"
    assert org["users"] == []


def test_get_organization_inexistente_retorna_none():
    auth = PlatformAuth()

    assert auth.get_organization("does-not-exist") is None


def test_add_user_to_organization_registra_usuario():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.register_user(_EMAIL, _PASSWORD, organization_id=org_id)

    org = auth.get_organization(org_id)

    assert _EMAIL in org["users"]


def test_dois_usuarios_na_mesma_org_compartilham_org_id():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.register_user("a@test.com", _PASSWORD, organization_id=org_id)
    auth.register_user("b@test.com", _PASSWORD, organization_id=org_id)

    assert auth.get_user_organization("a@test.com") == org_id
    assert auth.get_user_organization("b@test.com") == org_id

    org = auth.get_organization(org_id)
    assert "a@test.com" in org["users"]
    assert "b@test.com" in org["users"]


def test_usuarios_sem_org_explicita_ficam_em_organizacoes_diferentes():
    auth = PlatformAuth()

    auth.register_user("a@test.com", _PASSWORD)
    auth.register_user("b@test.com", _PASSWORD)

    assert auth.get_user_organization("a@test.com") != auth.get_user_organization("b@test.com")


def test_get_user_organization_usuario_inexistente_retorna_none():
    auth = PlatformAuth()

    assert auth.get_user_organization("ghost@test.com") is None


def test_session_contem_organization_id():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.register_user(_EMAIL, _PASSWORD, organization_id=org_id)

    session = auth.login(_EMAIL, _PASSWORD)
    full_session = auth.get_session(session["token"])

    assert full_session["organization_id"] == org_id
    assert full_session["role"] == "user"
    assert full_session["permissions"] == []


def test_login_retorno_publico_nao_muda():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    session = auth.login(_EMAIL, _PASSWORD)

    assert set(session.keys()) == {"token", "email"}


def test_organizacao_inicia_com_plano_free():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    assert auth.get_organization_plan(org_id) == "free"


def test_get_plan_limits_free():
    auth = PlatformAuth()

    limits = auth.get_plan_limits("free")

    assert limits == {"users": 1, "requests_per_day": 100, "projects": 1}


def test_get_plan_limits_plano_desconhecido_retorna_vazio():
    auth = PlatformAuth()

    assert auth.get_plan_limits("does-not-exist") == {}


def test_set_organization_plan_atualiza_plano():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.set_organization_plan(org_id, "pro")

    assert auth.get_organization_plan(org_id) == "pro"


def test_set_organization_plan_invalido_levanta_value_error():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    with pytest.raises(ValueError):
        auth.set_organization_plan(org_id, "does-not-exist")


def test_set_organization_plan_org_inexistente_levanta_lookup_error():
    auth = PlatformAuth()

    with pytest.raises(LookupError):
        auth.set_organization_plan("does-not-exist", "pro")


# --- Sprint 275: plan_history -------------------------------------------


def test_set_organization_plan_registra_historico():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.set_organization_plan(org_id, "pro")

    history = auth.list_organizations()[org_id]["plan_history"]
    assert len(history) == 1
    assert history[0]["from"] == "free"
    assert history[0]["to"] == "pro"
    assert isinstance(history[0]["timestamp"], int)


def test_set_organization_plan_acumula_multiplas_mudancas():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.set_organization_plan(org_id, "pro")
    auth.set_organization_plan(org_id, "enterprise")

    history = auth.list_organizations()[org_id]["plan_history"]
    assert [h["to"] for h in history] == ["pro", "enterprise"]


def test_set_organization_plan_para_o_mesmo_plano_nao_registra_historico():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.set_organization_plan(org_id, "pro")

    auth.set_organization_plan(org_id, "pro")

    history = auth.list_organizations()[org_id]["plan_history"]
    assert len(history) == 1


def test_set_organization_plan_invalido_nao_registra_historico():
    """A rejected plan change (ValueError) must not leave a phantom
    entry in plan_history — the org's plan never actually changed."""
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    with pytest.raises(ValueError):
        auth.set_organization_plan(org_id, "does-not-exist")

    assert "plan_history" not in auth.list_organizations()[org_id]


def test_set_organization_plan_ainda_invalida_cache_apos_mudanca():
    """Regression guard: the spec's own replacement for this method
    dropped `_invalidate_org_cache()` entirely, which would have left
    get_organization_plan() serving a stale cached value after an
    upgrade."""
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    org_id = auth.create_organization("Acme")
    auth.get_organization_plan(org_id)

    auth.set_organization_plan(org_id, "pro")

    assert auth.get_organization_plan(org_id) == "pro"


def test_get_user_organization_role():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    assert auth.get_user_organization_role(_EMAIL) == "owner"


def test_has_any_admin_falso_sem_usuarios():
    auth = PlatformAuth()

    assert auth.has_any_admin() is False


def test_has_any_admin_falso_so_com_usuarios_comuns():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD)

    assert auth.has_any_admin() is False


def test_has_any_admin_verdadeiro_apos_registrar_admin():
    auth = PlatformAuth()
    auth.register_user(_EMAIL, _PASSWORD, role="admin")

    assert auth.has_any_admin() is True


def test_check_limit_users_bloqueia_no_plano_free():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.register_user(_EMAIL, _PASSWORD, organization_id=org_id)

    with pytest.raises(PermissionError):
        auth.check_limit(org_id, "users")


def test_check_limit_users_permite_dentro_do_plano_pro():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.set_organization_plan(org_id, "pro")
    auth.register_user(_EMAIL, _PASSWORD, organization_id=org_id)

    auth.check_limit(org_id, "users")


def test_check_limit_enterprise_nunca_bloqueia():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.set_organization_plan(org_id, "enterprise")

    for i in range(10):
        auth.register_user(f"user{i}@test.com", _PASSWORD, organization_id=org_id)

    auth.check_limit(org_id, "users")


def test_check_limit_requests_per_day_bloqueia_apos_limite():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    for _ in range(100):
        auth.check_limit(org_id, "requests_per_day")
        auth.increment_usage(org_id, "requests_per_day")

    with pytest.raises(PermissionError):
        auth.check_limit(org_id, "requests_per_day")


def test_increment_usage_incrementa_contador():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.increment_usage(org_id, "requests_per_day")
    auth.increment_usage(org_id, "requests_per_day")

    assert auth._usage_record(org_id)["requests_today"] == 2


def test_reset_diario_zera_contador():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.increment_usage(org_id, "requests_per_day")
    assert auth._usage_record(org_id)["requests_today"] == 1

    auth._usage[org_id]["last_reset"] -= 1

    assert auth._usage_record(org_id)["requests_today"] == 0


def test_check_limit_projects_nao_bloqueia_sem_tracking():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.check_limit(org_id, "projects")


# --- Sprint 269: Stripe customer/subscription ids + status ---------------


def test_set_stripe_ids_grava_ambos():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.set_stripe_ids(org_id, "cus_123", "sub_456")

    assert auth.get_stripe_ids(org_id) == {
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_456",
    }


def test_set_stripe_ids_omitindo_um_nao_apaga_o_outro():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.set_stripe_ids(org_id, "cus_123", "sub_456")

    auth.set_stripe_ids(org_id, None, "sub_789")

    assert auth.get_stripe_ids(org_id) == {
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_789",
    }


def test_set_stripe_ids_organizacao_inexistente_lanca_lookup_error():
    auth = PlatformAuth()

    with pytest.raises(LookupError):
        auth.set_stripe_ids("does-not-exist", "cus_123", "sub_456")


def test_get_stripe_ids_organizacao_inexistente_retorna_vazio():
    auth = PlatformAuth()

    assert auth.get_stripe_ids("does-not-exist") == {}


def test_get_stripe_ids_sem_ids_definidos_retorna_none_para_ambos():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    assert auth.get_stripe_ids(org_id) == {
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
    }


def test_find_organization_by_stripe_customer_encontra_a_organizacao():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.set_stripe_ids(org_id, "cus_123", "sub_456")

    assert auth.find_organization_by_stripe_customer("cus_123") == org_id


def test_find_organization_by_stripe_customer_nao_encontrado_retorna_none():
    auth = PlatformAuth()

    assert auth.find_organization_by_stripe_customer("cus_does_not_exist") is None


def test_find_organization_by_stripe_customer_e_isolado():
    auth = PlatformAuth()
    org_a = auth.create_organization("Acme A")
    org_b = auth.create_organization("Acme B")
    auth.set_stripe_ids(org_a, "cus_a", "sub_a")
    auth.set_stripe_ids(org_b, "cus_b", "sub_b")

    assert auth.find_organization_by_stripe_customer("cus_b") == org_b


def test_set_subscription_status_funciona():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.set_subscription_status(org_id, "past_due")

    assert auth.get_subscription_status(org_id) == "past_due"


def test_set_subscription_status_organizacao_inexistente_lanca_lookup_error():
    auth = PlatformAuth()

    with pytest.raises(LookupError):
        auth.set_subscription_status("does-not-exist", "past_due")


def test_get_subscription_status_padrao_e_none():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    assert auth.get_subscription_status(org_id) is None


def test_get_subscription_status_organizacao_inexistente_retorna_none():
    auth = PlatformAuth()

    assert auth.get_subscription_status("does-not-exist") is None


# --- Sprint 270: get_usage_limit() ----------------------------------------


def test_get_usage_limit_resolve_pelo_plano_do_tenant_nao_pelo_tenant_id():
    """The core bug in the spec's own version: it called
    `get_plan_limits(tenant_id)` directly, but `get_plan_limits()` takes
    a *plan name*, not a tenant id. A tenant_id would never match any
    real plan key, so it would always fall through to the -1 default —
    silently making every tenant appear unlimited regardless of their
    actual plan."""
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    assert auth.get_usage_limit(org_id, "alerts_per_hour") == 50  # free plan's real limit


def test_get_usage_limit_reflete_upgrade_de_plano():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.set_organization_plan(org_id, "pro")

    assert auth.get_usage_limit(org_id, "alerts_per_hour") == 500


def test_get_usage_limit_enterprise_e_ilimitado():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    auth.set_organization_plan(org_id, "enterprise")

    assert auth.get_usage_limit(org_id, "alerts_per_hour") == -1


def test_get_usage_limit_metrica_desconhecida_retorna_ilimitado():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    assert auth.get_usage_limit(org_id, "not_a_real_metric") == -1


def test_get_usage_limit_organizacao_inexistente_retorna_ilimitado():
    auth = PlatformAuth()

    assert auth.get_usage_limit("does-not-exist", "alerts_per_hour") == -1


# --- Sprint 285: lead_states ---------------------------------------------


def test_get_lead_state_padrao_e_pending():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    assert auth.get_lead_state(org_id, "upgrade_offer") == "pending"


def test_set_lead_state_e_get_lead_state_round_trip():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.set_lead_state(org_id, "upgrade_offer", "contacted")

    assert auth.get_lead_state(org_id, "upgrade_offer") == "contacted"


def test_set_lead_state_e_por_lead_type_independente():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.set_lead_state(org_id, "upgrade_offer", "contacted")

    assert auth.get_lead_state(org_id, "upgrade_offer") == "contacted"
    assert auth.get_lead_state(org_id, "retention_offer") == "pending"


def test_set_lead_state_estado_invalido_levanta_value_error():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    with pytest.raises(ValueError):
        auth.set_lead_state(org_id, "upgrade_offer", "not-a-real-state")


def test_set_lead_state_organizacao_inexistente_levanta_lookup_error():
    auth = PlatformAuth()

    with pytest.raises(LookupError):
        auth.set_lead_state("does-not-exist", "upgrade_offer", "contacted")


def test_get_lead_state_organizacao_inexistente_retorna_pending():
    auth = PlatformAuth()

    assert auth.get_lead_state("does-not-exist", "upgrade_offer") == "pending"


def test_set_lead_state_sobrescreve_estado_anterior():
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")

    auth.set_lead_state(org_id, "upgrade_offer", "contacted")
    auth.set_lead_state(org_id, "upgrade_offer", "converted")

    assert auth.get_lead_state(org_id, "upgrade_offer") == "converted"
