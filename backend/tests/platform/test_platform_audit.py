import pytest

from app.platform.audit.platform_audit import PlatformAudit
from app.platform.auth.platform_auth import PlatformAuth
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.rate_limit.platform_rate_limiter import RateLimitExceeded
from app.platform.storage.platform_storage import FileStorage


def test_log_event_registra_evento_corretamente():
    audit = PlatformAudit()

    audit.log_event("user_registered", "user@test.com", "org1", {"role": "admin"})

    events = audit.get_events()
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "user_registered"
    assert event["email"] == "user@test.com"
    assert event["organization_id"] == "org1"
    assert event["metadata"] == {"role": "admin"}
    assert "timestamp" in event


def test_log_event_aceita_email_e_org_none():
    audit = PlatformAudit()

    audit.log_event("organization_created", None, "org1", {"name": "Acme"})

    event = audit.get_events()[0]
    assert event["email"] is None
    assert event["organization_id"] == "org1"


def test_log_event_sem_metadata_usa_dict_vazio():
    audit = PlatformAudit()

    audit.log_event("user_logged_out", "user@test.com", "org1")

    assert audit.get_events()[0]["metadata"] == {}


def test_metadata_e_preservada_sem_mutacao():
    audit = PlatformAudit()
    metadata = {"plan": "pro", "nested": {"a": 1}}

    audit.log_event("plan_upgraded", "user@test.com", "org1", metadata)

    assert audit.get_events()[0]["metadata"] == {"plan": "pro", "nested": {"a": 1}}


def test_get_events_retorna_mais_recente_primeiro():
    audit = PlatformAudit()

    audit.log_event("a", "user@test.com", "org1")
    audit.log_event("b", "user@test.com", "org1")
    audit.log_event("c", "user@test.com", "org1")

    events = audit.get_events()
    assert [e["event"] for e in events] == ["c", "b", "a"]


def test_get_events_retorna_copia():
    audit = PlatformAudit()
    audit.log_event("a", "user@test.com", "org1")

    events = audit.get_events()
    events.append({"fake": "event"})

    assert len(audit.get_events()) == 1


def test_get_events_vazio_por_padrao():
    audit = PlatformAudit()

    assert audit.get_events() == []


def test_platform_auth_sem_audit_nao_gera_eventos_nem_quebra():
    auth = PlatformAuth()

    auth.register_user("user@test.com", "123456")
    session = auth.login("user@test.com", "123456")
    auth.logout(session["token"])

    assert auth.exists("user@test.com")


def test_register_user_gera_evento_sem_dados_sensiveis():
    audit = PlatformAudit()
    auth = PlatformAuth(audit=audit)

    auth.register_user("user@test.com", "super-secret-password", role="admin")

    events = audit.get_events()
    event_names = [e["event"] for e in events]
    assert "user_registered" in event_names
    assert "organization_created" in event_names
    assert "user_added_to_org" in event_names

    for event in events:
        serialized = str(event)
        assert "super-secret-password" not in serialized
        assert "salt" not in serialized
        assert "hash" not in serialized


def test_login_gera_evento_sem_token_nem_senha():
    audit = PlatformAudit()
    auth = PlatformAuth(audit=audit)
    auth.register_user("user@test.com", "123456")

    session = auth.login("user@test.com", "123456")

    login_events = [e for e in audit.get_events() if e["event"] == "user_logged_in"]
    assert len(login_events) == 1
    assert login_events[0]["email"] == "user@test.com"
    assert session["token"] not in str(login_events[0])


def test_login_com_credenciais_invalidas_nao_gera_evento():
    audit = PlatformAudit()
    auth = PlatformAuth(audit=audit)
    auth.register_user("user@test.com", "123456")

    auth.login("user@test.com", "wrong-password")

    login_events = [e for e in audit.get_events() if e["event"] == "user_logged_in"]
    assert login_events == []


def test_logout_gera_evento():
    audit = PlatformAudit()
    auth = PlatformAuth(audit=audit)
    auth.register_user("user@test.com", "123456")
    session = auth.login("user@test.com", "123456")

    auth.logout(session["token"])

    logout_events = [e for e in audit.get_events() if e["event"] == "user_logged_out"]
    assert len(logout_events) == 1
    assert logout_events[0]["email"] == "user@test.com"


def test_logout_com_token_invalido_nao_gera_evento():
    audit = PlatformAudit()
    auth = PlatformAuth(audit=audit)

    auth.logout("not-a-real-token")

    assert audit.get_events() == []


def test_upgrade_plan_gera_evento():
    audit = PlatformAudit()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=audit)
    container.auth().register_user("owner@test.com", "123456")
    container.login("owner@test.com", "123456")

    container.upgrade_plan("pro")

    plan_events = [e for e in audit.get_events() if e["event"] == "plan_upgraded"]
    assert len(plan_events) == 1
    assert plan_events[0]["metadata"] == {"plan": "pro"}


def test_rate_limit_exceeded_gera_evento():
    audit = PlatformAudit()
    auth = PlatformAuth(audit=audit)
    auth.register_user("user@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("user@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("user@test.com")

    rate_events = [e for e in audit.get_events() if e["event"] == "rate_limit_exceeded"]
    assert len(rate_events) == 1
    assert rate_events[0]["email"] == "user@test.com"


def test_container_sem_audit_nao_quebra():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456", role="admin")

    container.login("user@test.com", "123456")

    assert container.current_user_role() == "admin"
    container.require_role("admin")


def test_require_auth_gera_evento_de_acesso_negado():
    audit = PlatformAudit()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=audit)

    with pytest.raises(PermissionError):
        container.require_auth()

    events = [e for e in audit.get_events() if e["event"] == "auth_checked"]
    assert len(events) == 1
    assert events[0]["metadata"]["result"] == "denied"
    assert events[0]["email"] is None


def test_require_role_gera_evento_de_acesso_concedido_e_negado():
    audit = PlatformAudit()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=audit)
    container.auth().register_user("user@test.com", "123456", role="user")
    container.login("user@test.com", "123456")

    container.require_role("user")

    with pytest.raises(PermissionError):
        container.require_role("admin")

    role_events = [e for e in audit.get_events() if e["event"] == "role_checked"]
    assert len(role_events) == 2
    # get_events() returns most-recent-first: "admin" (denied) was checked after "user" (granted).
    assert role_events[0]["metadata"] == {"required_role": "admin", "result": "denied"}
    assert role_events[1]["metadata"] == {"required_role": "user", "result": "granted"}


def test_require_permission_gera_evento():
    audit = PlatformAudit()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=audit)
    container.auth().register_user("user@test.com", "123456", permissions=["read"])
    container.login("user@test.com", "123456")

    container.require_permission("read")

    permission_events = [e for e in audit.get_events() if e["event"] == "permission_checked"]
    assert len(permission_events) == 1
    assert permission_events[0]["metadata"] == {"required_permission": "read", "result": "granted"}


def test_integracao_completa_container_com_audit():
    audit = PlatformAudit()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=audit)

    container.auth().register_user("owner@test.com", "123456", role="admin")
    container.login("owner@test.com", "123456")
    container.require_role("admin")
    container.upgrade_plan("pro")
    container.logout()

    event_names = [e["event"] for e in audit.get_events()]

    assert "user_registered" in event_names
    assert "user_logged_in" in event_names
    assert "role_checked" in event_names
    assert "plan_upgraded" in event_names
    assert "user_logged_out" in event_names


def test_persistencia_via_file_storage(tmp_path):
    path = str(tmp_path / "audit.json")
    audit1 = PlatformAudit(storage=FileStorage(path))
    audit1.log_event("user_registered", "user@test.com", "org1", {"role": "admin"})

    audit2 = PlatformAudit(storage=FileStorage(path))
    events = audit2.get_events()

    assert len(events) == 1
    assert events[0]["event"] == "user_registered"
    assert events[0]["metadata"] == {"role": "admin"}


def test_persistencia_acumula_entre_instancias(tmp_path):
    path = str(tmp_path / "audit.json")

    audit1 = PlatformAudit(storage=FileStorage(path))
    audit1.log_event("a", "user@test.com", "org1")

    audit2 = PlatformAudit(storage=FileStorage(path))
    audit2.log_event("b", "user@test.com", "org1")

    audit3 = PlatformAudit(storage=FileStorage(path))
    events = audit3.get_events()

    assert [e["event"] for e in events] == ["b", "a"]


def test_persistencia_nao_grava_dados_sensiveis(tmp_path):
    path = str(tmp_path / "audit.json")
    audit = PlatformAudit(storage=FileStorage(path))
    auth = PlatformAuth(audit=audit)

    auth.register_user("user@test.com", "super-secret-password")

    with open(path, encoding="utf-8") as f:
        raw = f.read()

    assert "super-secret-password" not in raw
    assert "salt" not in raw
    assert "hash" not in raw


def test_sem_storage_permanece_apenas_em_memoria():
    audit = PlatformAudit()

    audit.log_event("a", "user@test.com", "org1")

    assert audit._storage is None
    assert len(audit.get_events()) == 1


def test_filtro_por_email():
    audit = PlatformAudit()
    audit.log_event("a", "user1@test.com", "org1")
    audit.log_event("b", "user2@test.com", "org1")

    events = audit.get_events(email="user1@test.com")

    assert len(events) == 1
    assert events[0]["email"] == "user1@test.com"


def test_filtro_por_organization_id():
    audit = PlatformAudit()
    audit.log_event("a", "user@test.com", "org1")
    audit.log_event("b", "user@test.com", "org2")

    events = audit.get_events(organization_id="org2")

    assert len(events) == 1
    assert events[0]["organization_id"] == "org2"


def test_filtro_por_event():
    audit = PlatformAudit()
    audit.log_event("user_logged_in", "user@test.com", "org1")
    audit.log_event("user_logged_out", "user@test.com", "org1")

    events = audit.get_events(event="user_logged_out")

    assert len(events) == 1
    assert events[0]["event"] == "user_logged_out"


def test_filtros_combinados():
    audit = PlatformAudit()
    audit.log_event("user_logged_in", "user1@test.com", "org1")
    audit.log_event("user_logged_in", "user2@test.com", "org1")
    audit.log_event("user_logged_out", "user1@test.com", "org1")

    events = audit.get_events(email="user1@test.com", event="user_logged_in")

    assert len(events) == 1
    assert events[0]["email"] == "user1@test.com"
    assert events[0]["event"] == "user_logged_in"


def test_filtro_sem_correspondencia_retorna_vazio():
    audit = PlatformAudit()
    audit.log_event("a", "user@test.com", "org1")

    assert audit.get_events(email="ghost@test.com") == []


def test_limit_respeitado():
    audit = PlatformAudit()
    for i in range(10):
        audit.log_event(f"event_{i}", "user@test.com", "org1")

    events = audit.get_events(limit=3)

    assert len(events) == 3
    assert [e["event"] for e in events] == ["event_9", "event_8", "event_7"]


def test_limit_default_e_100():
    audit = PlatformAudit()
    for i in range(150):
        audit.log_event(f"event_{i}", "user@test.com", "org1")

    events = audit.get_events()

    assert len(events) == 100
    assert events[0]["event"] == "event_149"


def test_limit_zero_retorna_vazio():
    audit = PlatformAudit()
    audit.log_event("a", "user@test.com", "org1")

    assert audit.get_events(limit=0) == []


def test_filtro_aplicado_antes_do_limit():
    audit = PlatformAudit()
    for i in range(5):
        audit.log_event("noise", "other@test.com", "org1")
    audit.log_event("target", "user@test.com", "org1")

    events = audit.get_events(email="user@test.com", limit=1)

    assert len(events) == 1
    assert events[0]["event"] == "target"


def test_limite_de_memoria_in_memory_descarta_mais_antigos():
    audit = PlatformAudit()

    for i in range(10_050):
        audit.log_event(f"event_{i}", "user@test.com", "org1", {})

    assert len(audit._events) == 10_000
    assert audit._events[0]["event"] == "event_50"
    assert audit._events[-1]["event"] == "event_10049"


def test_limite_de_memoria_nao_se_aplica_com_storage(tmp_path):
    path = str(tmp_path / "audit.json")
    audit = PlatformAudit(storage=FileStorage(path))
    audit._events = [
        {
            "event": f"old_{i}",
            "email": None,
            "organization_id": None,
            "metadata": {},
            "timestamp": "x",
        }
        for i in range(10_000)
    ]

    audit.log_event("new_event", "user@test.com", "org1", {})

    assert len(audit._events) == 10_001
