from unittest.mock import MagicMock, patch

from app.platform.auth.platform_auth import PlatformAuth
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.storage.postgres_storage import PostgresStorage


def _mock_connection(fetchone_return=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_return

    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor

    return conn, cursor


def _fake_postgres_backend():
    """Simulates a real `platform_data` table (id=1, payload jsonb) in memory,
    so PostgresStorage can be exercised end-to-end without a live server.
    """
    backing_store: dict = {}

    def connect(dsn):
        conn = MagicMock()
        cursor = MagicMock()

        def execute(sql, params=None):
            if "CREATE TABLE" in sql:
                return
            if "INSERT INTO platform_data" in sql:
                backing_store["payload"] = params[0].adapted
                return
            if "SELECT payload" in sql:
                cursor.fetchone.return_value = (
                    (backing_store["payload"],) if "payload" in backing_store else None
                )

        cursor.execute.side_effect = execute
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor

        return conn

    return connect


def test_init_db_cria_tabela_se_nao_existir():
    conn, cursor = _mock_connection()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", return_value=conn):
        PostgresStorage("postgresql://fake-dsn")

    calls = cursor.execute.call_args_list
    create_calls = [call for call in calls if "CREATE TABLE" in call.args[0]]

    assert len(create_calls) == 1
    assert "platform_data" in create_calls[0].args[0]
    assert conn.close.called


def test_load_retorna_vazio_quando_nao_ha_linha():
    conn, cursor = _mock_connection(fetchone_return=None)

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", return_value=conn):
        storage = PostgresStorage("postgresql://fake-dsn")
        result = storage.load()

    assert result == {}


def test_load_retorna_payload_existente():
    payload = {"users": {"a@test.com": {"role": "user"}}}
    conn, cursor = _mock_connection(fetchone_return=(payload,))

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", return_value=conn):
        storage = PostgresStorage("postgresql://fake-dsn")
        result = storage.load()

    assert result == payload


def test_load_decodifica_bytes():
    payload = {"users": {"a@test.com": {"salt": {"__bytes__": "AAH/"}}}}
    conn, cursor = _mock_connection(fetchone_return=(payload,))

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", return_value=conn):
        storage = PostgresStorage("postgresql://fake-dsn")
        result = storage.load()

    assert result["users"]["a@test.com"]["salt"] == b"\x00\x01\xff"


def test_save_executa_upsert_com_payload_codificado():
    conn, cursor = _mock_connection()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", return_value=conn):
        storage = PostgresStorage("postgresql://fake-dsn")
        storage.save({"users": {"a@test.com": {"salt": b"\x00\x01\xff"}}})

    calls = cursor.execute.call_args_list
    upsert_calls = [call for call in calls if "INSERT INTO platform_data" in call.args[0]]

    assert len(upsert_calls) == 1
    assert "ON CONFLICT" in upsert_calls[0].args[0]

    encoded_payload = upsert_calls[0].args[1][0]
    assert encoded_payload.adapted == {"users": {"a@test.com": {"salt": {"__bytes__": "AAH/"}}}}


def test_storage_salva_e_carrega_dados():
    connect = _fake_postgres_backend()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        storage = PostgresStorage("postgresql://fake-dsn")
        storage.save({"organizations": {"org1": {"name": "Acme", "plan": "free"}}})

        assert storage.load() == {"organizations": {"org1": {"name": "Acme", "plan": "free"}}}


def test_persistencia_entre_instancias_funciona_igual_ao_file_storage():
    connect = _fake_postgres_backend()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        storage1 = PostgresStorage("postgresql://fake-dsn")
        storage1.save({"organizations": {"org1": {"name": "Acme", "plan": "free"}}})

        storage2 = PostgresStorage("postgresql://fake-dsn")
        result = storage2.load()

    assert result == {"organizations": {"org1": {"name": "Acme", "plan": "free"}}}


def test_usuarios_persistem_entre_instancias_com_postgres_storage():
    connect = _fake_postgres_backend()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        auth1 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))
        auth1.register_user("user@test.com", "123456")

        auth2 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))

        assert auth2.exists("user@test.com")


def test_login_funciona_apos_reload_com_postgres_storage():
    connect = _fake_postgres_backend()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        auth1 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))
        auth1.register_user("user@test.com", "123456")

        auth2 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))
        session = auth2.login("user@test.com", "123456")

    assert session is not None
    assert session["email"] == "user@test.com"


def test_organizacao_e_plano_persistem_entre_instancias_com_postgres_storage():
    connect = _fake_postgres_backend()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        auth1 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))
        org_id = auth1.create_organization("Acme")
        auth1.set_organization_plan(org_id, "pro")

        auth2 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))

        assert auth2.get_organization(org_id) is not None
        assert auth2.get_organization_plan(org_id) == "pro"


def test_usage_persiste_entre_instancias_com_postgres_storage():
    connect = _fake_postgres_backend()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        auth1 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))
        org_id = auth1.create_organization("Acme")
        auth1.increment_usage(org_id, "requests_per_day")
        auth1.increment_usage(org_id, "requests_per_day")

        auth2 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))

        assert auth2._usage_record(org_id)["requests_today"] == 2


def test_sessoes_nao_persistem_com_postgres_storage():
    connect = _fake_postgres_backend()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        auth1 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))
        auth1.register_user("user@test.com", "123456")
        session = auth1.login("user@test.com", "123456")

        auth2 = PlatformAuth(storage=PostgresStorage("postgresql://fake-dsn"))

        assert auth2.is_authenticated(session["token"]) is False


def _fake_postgres_backend_multi_row():
    """Simulates the `platform_data` table with several rows, keyed by `id` or
    `organization_id` — the richer fake needed to exercise tenant-scoped storage,
    as opposed to `_fake_postgres_backend`'s single legacy `id=1` row.
    """
    rows: dict[int, dict] = {}

    def connect(dsn):
        conn = MagicMock()
        cursor = MagicMock()
        state: dict = {}

        def execute(sql, params=None):
            if "CREATE TABLE" in sql or "ALTER TABLE" in sql:
                return
            if "SELECT id FROM platform_data WHERE organization_id" in sql:
                org_id = params[0]
                match = next(
                    ((rid, r) for rid, r in rows.items() if r["organization_id"] == org_id),
                    None,
                )
                state["last_row"] = (match[0],) if match else None
                return
            if "SELECT payload FROM platform_data WHERE organization_id" in sql:
                org_id = params[0]
                match = next(
                    (r for r in rows.values() if r["organization_id"] == org_id), None
                )
                state["last_row"] = (match["payload"],) if match else None
                return
            if "SELECT payload FROM platform_data WHERE id = 1" in sql:
                match = rows.get(1)
                state["last_row"] = (match["payload"],) if match else None
                return
            if "UPDATE platform_data SET payload" in sql:
                encoded, row_id = params
                rows[row_id]["payload"] = encoded.adapted
                return
            if "INSERT INTO platform_data (id, organization_id, payload)" in sql:
                org_id, encoded = params
                next_id = (max(rows.keys()) + 1) if rows else 1
                rows[next_id] = {"organization_id": org_id, "payload": encoded.adapted}
                return
            if "INSERT INTO platform_data (id, payload)" in sql:
                encoded = params[0]
                rows[1] = {"organization_id": None, "payload": encoded.adapted}
                return

        cursor.execute.side_effect = execute
        cursor.fetchone.side_effect = lambda: state.get("last_row")
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor

        return conn

    return connect


def test_init_db_adiciona_coluna_organization_id():
    conn, cursor = _mock_connection()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", return_value=conn):
        PostgresStorage("postgresql://fake-dsn")

    calls = cursor.execute.call_args_list
    alter_calls = [call for call in calls if "ALTER TABLE" in call.args[0]]

    assert len(alter_calls) == 1
    assert "organization_id" in alter_calls[0].args[0]


def test_sem_organization_id_mantem_comportamento_legado():
    conn, cursor = _mock_connection()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", return_value=conn):
        storage = PostgresStorage("postgresql://fake-dsn")

    assert storage._organization_id is None


def test_organization_id_isola_dados_entre_tenants():
    connect = _fake_postgres_backend_multi_row()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        storage_a = PostgresStorage("postgresql://fake-dsn", organization_id="org-a")
        storage_a.save({"users": {"a@test.com": {}}})

        storage_b = PostgresStorage("postgresql://fake-dsn", organization_id="org-b")
        storage_b.save({"users": {"b@test.com": {}}})

        assert storage_a.load() == {"users": {"a@test.com": {}}}
        assert storage_b.load() == {"users": {"b@test.com": {}}}


def test_organization_id_none_nao_interfere_com_dados_de_tenant():
    connect = _fake_postgres_backend_multi_row()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        legacy = PostgresStorage("postgresql://fake-dsn")
        legacy.save({"legacy": True})

        tenant = PostgresStorage("postgresql://fake-dsn", organization_id="org-a")
        tenant.save({"tenant": True})

        assert legacy.load() == {"legacy": True}
        assert tenant.load() == {"tenant": True}


def test_save_para_mesmo_tenant_atualiza_a_mesma_linha():
    connect = _fake_postgres_backend_multi_row()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        storage1 = PostgresStorage("postgresql://fake-dsn", organization_id="org-a")
        storage1.save({"v": 1})

        storage2 = PostgresStorage("postgresql://fake-dsn", organization_id="org-a")
        storage2.save({"v": 2})

        assert storage2.load() == {"v": 2}


def test_load_organization_id_sem_dados_retorna_vazio():
    connect = _fake_postgres_backend_multi_row()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        storage = PostgresStorage("postgresql://fake-dsn", organization_id="org-ghost")

        assert storage.load() == {}


def test_platform_auth_isolado_por_organization_id_via_postgres():
    connect = _fake_postgres_backend_multi_row()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        auth_a = PlatformAuth(
            storage=PostgresStorage("postgresql://fake-dsn", organization_id="org-a")
        )
        auth_a.register_user("user@test.com", "123456")

        auth_b = PlatformAuth(
            storage=PostgresStorage("postgresql://fake-dsn", organization_id="org-b")
        )

        assert auth_b.exists("user@test.com") is False


def test_container_repassa_postgres_storage_para_auth():
    connect = _fake_postgres_backend()

    with patch("app.platform.storage.postgres_storage.psycopg2.connect", side_effect=connect):
        container1 = PlatformContainer(
            bootstrap=PlatformBootstrap(), storage=PostgresStorage("postgresql://fake-dsn")
        )
        container1.auth().register_user("user@test.com", "123456")

        container2 = PlatformContainer(
            bootstrap=PlatformBootstrap(), storage=PostgresStorage("postgresql://fake-dsn")
        )

        assert container2.auth().exists("user@test.com")
