from app.platform.auth.platform_auth import PlatformAuth
from app.platform.logging.platform_logger import PlatformLogger


def test_get_logs_filtra_por_organization_id_do_metadata():
    logger = PlatformLogger()

    logger.log("INFO", "a", metadata={"organization_id": "org-a"})
    logger.log("INFO", "b", metadata={"organization_id": "org-b"})

    logs = logger.get_logs(organization_id="org-a")
    assert len(logs) == 1
    assert logs[0]["message"] == "a"


def test_get_logs_sem_filtro_retorna_tudo():
    logger = PlatformLogger()

    logger.log("INFO", "a", metadata={"organization_id": "org-a"})
    logger.log("INFO", "b", metadata={"organization_id": "org-b"})
    logger.log("INFO", "c")

    assert len(logger.get_logs()) == 3


def test_get_logs_entrada_sem_organization_id_nao_aparece_em_filtro_especifico():
    logger = PlatformLogger()

    logger.log("INFO", "sem_org")

    assert logger.get_logs(organization_id="org-a") == []


def test_filtro_por_organization_id_combinado_com_level():
    logger = PlatformLogger()

    logger.log("WARN", "w1", metadata={"organization_id": "org-a"})
    logger.log("INFO", "i1", metadata={"organization_id": "org-a"})
    logger.log("WARN", "w2", metadata={"organization_id": "org-b"})

    logs = logger.get_logs(level="WARN", organization_id="org-a")
    assert len(logs) == 1
    assert logs[0]["message"] == "w1"


def test_limit_respeitado_apos_filtro_por_organization_id():
    logger = PlatformLogger()

    for i in range(5):
        logger.log("INFO", f"event_{i}", metadata={"organization_id": "org-a"})
    logger.log("INFO", "noise", metadata={"organization_id": "org-b"})

    logs = logger.get_logs(organization_id="org-a", limit=2)
    assert len(logs) == 2
    assert [entry["message"] for entry in logs] == ["event_4", "event_3"]


def test_ordem_mais_recente_primeiro_preservada_com_filtro():
    logger = PlatformLogger()

    logger.log("INFO", "a", metadata={"organization_id": "org-a"})
    logger.log("INFO", "b", metadata={"organization_id": "org-a"})
    logger.log("INFO", "c", metadata={"organization_id": "org-a"})

    logs = logger.get_logs(organization_id="org-a")
    assert [entry["message"] for entry in logs] == ["c", "b", "a"]


def test_platform_auth_isola_logs_entre_organizacoes():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)

    auth.register_user("a@test.com", "123456")
    auth.register_user("b@test.com", "123456")

    org_a = auth.get_user_organization("a@test.com")
    org_b = auth.get_user_organization("b@test.com")
    assert org_a != org_b

    logs_a = logger.get_logs(organization_id=org_a)
    logs_b = logger.get_logs(organization_id=org_b)

    assert any(e["message"] == "auth.register" and e["metadata"]["email"] == "a@test.com"
               for e in logs_a)
    assert all(e["metadata"].get("email") != "b@test.com" for e in logs_a)
    assert any(e["message"] == "auth.register" and e["metadata"]["email"] == "b@test.com"
               for e in logs_b)
    assert all(e["metadata"].get("email") != "a@test.com" for e in logs_b)


def test_platform_auth_login_falho_com_senha_errada_carrega_organization_id():
    """Regression guard: this metadata field is what makes tenant-scoped log
    filtering work for failed-password attempts — without it, a WARN-level
    failure would silently disappear from every tenant-scoped view.
    """
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)
    auth.register_user("user@test.com", "123456")
    org_id = auth.get_user_organization("user@test.com")

    auth.login("user@test.com", "wrong-password")

    logs = logger.get_logs(organization_id=org_id, level="WARN")
    assert any(e["message"] == "auth.login.failed" for e in logs)
