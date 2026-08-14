import pytest

from app.platform.auth.platform_auth import PlatformAuth
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.logging.platform_logger import PlatformLogger
from app.platform.rate_limit.platform_rate_limiter import RateLimitExceeded


def test_log_e_salvo_corretamente():
    logger = PlatformLogger()

    logger.log("INFO", "user_logged_in", correlation_id="corr-1", metadata={"email": "a@test.com"})

    logs = logger.get_logs()
    assert len(logs) == 1
    entry = logs[0]
    assert entry["level"] == "INFO"
    assert entry["message"] == "user_logged_in"
    assert entry["correlation_id"] == "corr-1"
    assert entry["metadata"] == {"email": "a@test.com"}
    assert "timestamp" in entry


def test_log_sem_correlation_id_nem_metadata():
    logger = PlatformLogger()

    logger.log("INFO", "x")

    entry = logger.get_logs()[0]
    assert entry["correlation_id"] is None
    assert entry["metadata"] == {}


def test_get_logs_retorna_mais_recente_primeiro():
    logger = PlatformLogger()

    logger.log("INFO", "a")
    logger.log("INFO", "b")
    logger.log("INFO", "c")

    assert [entry["message"] for entry in logger.get_logs()] == ["c", "b", "a"]


def test_get_logs_filtra_por_level():
    logger = PlatformLogger()

    logger.log("INFO", "ok")
    logger.log("WARN", "careful")
    logger.log("INFO", "ok again")

    warnings = logger.get_logs(level="WARN")
    assert len(warnings) == 1
    assert warnings[0]["message"] == "careful"


def test_get_logs_respeita_limit():
    logger = PlatformLogger()

    for i in range(10):
        logger.log("INFO", f"event_{i}")

    logs = logger.get_logs(limit=3)
    assert len(logs) == 3
    assert [entry["message"] for entry in logs] == ["event_9", "event_8", "event_7"]


def test_get_logs_limit_zero_retorna_vazio():
    logger = PlatformLogger()
    logger.log("INFO", "a")

    assert logger.get_logs(limit=0) == []


def test_get_logs_vazio_por_padrao():
    logger = PlatformLogger()

    assert logger.get_logs() == []


def test_get_logs_filtro_e_limit_combinados():
    logger = PlatformLogger()
    logger.log("WARN", "w1")
    logger.log("INFO", "i1")
    logger.log("WARN", "w2")
    logger.log("WARN", "w3")

    logs = logger.get_logs(level="WARN", limit=2)
    assert [entry["message"] for entry in logs] == ["w3", "w2"]


def test_platform_auth_sem_logger_nao_quebra():
    auth = PlatformAuth()

    auth.register_user("user@test.com", "123456")
    auth.login("user@test.com", "123456")
    auth.login("user@test.com", "wrong-password")

    assert auth.exists("user@test.com")


def test_register_user_gera_log_info():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)

    auth.register_user("user@test.com", "123456")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.register"]
    assert len(logs) == 1
    assert logs[0]["level"] == "INFO"
    assert logs[0]["metadata"]["email"] == "user@test.com"


def test_login_sucesso_gera_log_info():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)
    auth.register_user("user@test.com", "123456")

    auth.login("user@test.com", "123456")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.login.success"]
    assert len(logs) == 1
    assert logs[0]["level"] == "INFO"


def test_login_falha_senha_errada_gera_log_warn():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)
    auth.register_user("user@test.com", "123456")

    auth.login("user@test.com", "wrong-password")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.login.failed"]
    assert len(logs) == 1
    assert logs[0]["level"] == "WARN"


def test_login_falha_usuario_inexistente_gera_log_warn():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)

    auth.login("ghost@test.com", "whatever")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.login.failed"]
    assert len(logs) == 1
    assert logs[0]["metadata"]["email"] == "ghost@test.com"


def test_check_rate_limit_gera_log_warn_ao_bloquear():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)
    auth.register_user("user@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("user@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("user@test.com")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.rate_limited"]
    assert len(logs) == 1
    assert logs[0]["level"] == "WARN"


def test_correlation_id_propaga_para_o_log_de_login():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)
    auth.register_user("user@test.com", "123456")

    auth.login("user@test.com", "123456", correlation_id="corr-abc")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.login.success"]
    assert logs[0]["correlation_id"] == "corr-abc"


def test_correlation_id_propaga_para_login_falho():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)

    auth.login("ghost@test.com", "whatever", correlation_id="corr-xyz")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.login.failed"]
    assert logs[0]["correlation_id"] == "corr-xyz"


def test_correlation_id_propaga_para_register():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)

    auth.register_user("user@test.com", "123456", correlation_id="corr-reg")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.register"]
    assert logs[0]["correlation_id"] == "corr-reg"


def test_correlation_id_propaga_para_rate_limit():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)
    auth.register_user("user@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("user@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("user@test.com", correlation_id="corr-rl")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.rate_limited"]
    assert logs[0]["correlation_id"] == "corr-rl"


def test_logs_nunca_contem_senha_hash_ou_token():
    logger = PlatformLogger()
    auth = PlatformAuth(logger=logger)

    auth.register_user("user@test.com", "super-secret-password")
    session = auth.login("user@test.com", "super-secret-password")
    auth.login("user@test.com", "wrong-password")

    serialized = str(logger.get_logs())
    assert "super-secret-password" not in serialized
    assert "wrong-password" not in serialized
    assert session["token"] not in serialized
    assert "salt" not in serialized
    assert "hash" not in serialized


def test_container_repassa_logger_para_auth():
    logger = PlatformLogger()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), logger=logger)

    container.auth().register_user("user@test.com", "123456")

    logs = [e for e in logger.get_logs() if e["message"] == "auth.register"]
    assert len(logs) == 1


def test_container_sem_logger_funciona_normalmente():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    container.auth().register_user("user@test.com", "123456")
    session = container.login("user@test.com", "123456")

    assert session is not None
