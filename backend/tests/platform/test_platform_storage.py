import json

from app.platform.auth.platform_auth import PlatformAuth
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.storage.platform_storage import FileStorage, InMemoryStorage


def test_in_memory_storage_salva_e_carrega():
    storage = InMemoryStorage()

    storage.save({"users": {"a@test.com": {"role": "user"}}})

    assert storage.load() == {"users": {"a@test.com": {"role": "user"}}}


def test_in_memory_storage_carrega_vazio_por_padrao():
    storage = InMemoryStorage()

    assert storage.load() == {}


def test_file_storage_carrega_vazio_quando_arquivo_nao_existe(tmp_path):
    path = str(tmp_path / "does-not-exist.json")
    storage = FileStorage(path)

    assert storage.load() == {}


def test_file_storage_salva_e_carrega(tmp_path):
    path = str(tmp_path / "data.json")
    storage = FileStorage(path)

    storage.save({"organizations": {"org1": {"name": "Acme", "plan": "free"}}})

    assert storage.load() == {"organizations": {"org1": {"name": "Acme", "plan": "free"}}}


def test_file_storage_persiste_bytes_corretamente(tmp_path):
    path = str(tmp_path / "data.json")
    storage = FileStorage(path)

    storage.save({"users": {"a@test.com": {"salt": b"\x00\x01\xff", "hash": b"secret"}}})

    loaded = storage.load()

    assert loaded["users"]["a@test.com"]["salt"] == b"\x00\x01\xff"
    assert loaded["users"]["a@test.com"]["hash"] == b"secret"


def test_file_storage_escreve_json_valido(tmp_path):
    path = tmp_path / "data.json"
    storage = FileStorage(str(path))

    storage.save({"a": 1})

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    assert raw == {"a": 1}


def test_usuarios_persistem_entre_instancias_com_file_storage(tmp_path):
    path = str(tmp_path / "auth.json")

    auth1 = PlatformAuth(storage=FileStorage(path))
    auth1.register_user("user@test.com", "123456")

    auth2 = PlatformAuth(storage=FileStorage(path))

    assert auth2.exists("user@test.com")


def test_login_funciona_apos_reload_com_file_storage(tmp_path):
    path = str(tmp_path / "auth.json")

    auth1 = PlatformAuth(storage=FileStorage(path))
    auth1.register_user("user@test.com", "123456")

    auth2 = PlatformAuth(storage=FileStorage(path))
    session = auth2.login("user@test.com", "123456")

    assert session is not None
    assert session["email"] == "user@test.com"


def test_organizacao_e_plano_persistem_entre_instancias(tmp_path):
    path = str(tmp_path / "auth.json")

    auth1 = PlatformAuth(storage=FileStorage(path))
    org_id = auth1.create_organization("Acme")
    auth1.set_organization_plan(org_id, "pro")

    auth2 = PlatformAuth(storage=FileStorage(path))

    assert auth2.get_organization(org_id) is not None
    assert auth2.get_organization_plan(org_id) == "pro"


def test_usage_persiste_entre_instancias(tmp_path):
    path = str(tmp_path / "auth.json")

    auth1 = PlatformAuth(storage=FileStorage(path))
    org_id = auth1.create_organization("Acme")
    auth1.increment_usage(org_id, "requests_per_day")
    auth1.increment_usage(org_id, "requests_per_day")

    auth2 = PlatformAuth(storage=FileStorage(path))

    assert auth2.get_usage_for_org(org_id) == 2


def test_sessoes_nao_persistem(tmp_path):
    path = str(tmp_path / "auth.json")

    auth1 = PlatformAuth(storage=FileStorage(path))
    auth1.register_user("user@test.com", "123456")
    session = auth1.login("user@test.com", "123456")

    auth2 = PlatformAuth(storage=FileStorage(path))

    assert auth2.is_authenticated(session["token"]) is False


def test_platform_auth_sem_storage_usa_in_memory_por_padrao():
    auth = PlatformAuth()

    assert isinstance(auth._storage, InMemoryStorage)


def test_container_repassa_storage_para_auth(tmp_path):
    path = str(tmp_path / "auth.json")

    container1 = PlatformContainer(bootstrap=PlatformBootstrap(), storage=FileStorage(path))
    container1.auth().register_user("user@test.com", "123456")

    container2 = PlatformContainer(bootstrap=PlatformBootstrap(), storage=FileStorage(path))

    assert container2.auth().exists("user@test.com")


def test_container_sem_storage_mantem_isolamento_padrao():
    c1 = PlatformContainer(bootstrap=PlatformBootstrap())
    c1.auth().register_user("user@test.com", "123456")

    c2 = PlatformContainer(bootstrap=PlatformBootstrap())

    assert c2.auth().exists("user@test.com") is False
