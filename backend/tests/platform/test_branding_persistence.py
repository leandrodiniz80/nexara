import datetime
from dataclasses import replace
from unittest.mock import MagicMock, patch

from app.platform.audit.platform_audit import PlatformAudit
from app.platform.branding.branding_service import BrandingService
from app.platform.branding.branding_storage import (
    InMemoryBrandingStorage,
    PostgresBrandingStorage,
)
from app.platform.branding.nexara_theme import get_nexara_theme


def _custom_payload(color: str) -> dict:
    default = get_nexara_theme()
    return {
        "colors": {**default.colors.__dict__, "primary_bg": color},
        "typography": default.typography.__dict__,
        "spacing": default.spacing.__dict__,
    }


def _theme_with_primary_bg(color: str):
    default = get_nexara_theme()
    return replace(default, colors=replace(default.colors, primary_bg=color))


def test_in_memory_storage_salva_e_carrega_ultima_versao():
    storage = InMemoryBrandingStorage()

    storage.save_version("org-a", _custom_payload("#111111"))

    record = storage.load_latest("org-a")
    assert record["payload"]["colors"]["primary_bg"] == "#111111"
    assert record["version"] == 1


def test_in_memory_storage_sem_versao_retorna_none():
    storage = InMemoryBrandingStorage()

    assert storage.load_latest("org-ghost") is None


def test_in_memory_storage_versoes_incrementam():
    storage = InMemoryBrandingStorage()

    storage.save_version("org-a", _custom_payload("#111111"))
    storage.save_version("org-a", _custom_payload("#222222"))
    storage.save_version("org-a", _custom_payload("#333333"))

    latest = storage.load_latest("org-a")
    assert latest["version"] == 3
    assert latest["payload"]["colors"]["primary_bg"] == "#333333"


def test_in_memory_storage_list_versions_ordem_desc():
    storage = InMemoryBrandingStorage()

    storage.save_version("org-a", _custom_payload("#111111"))
    storage.save_version("org-a", _custom_payload("#222222"))

    versions = storage.list_versions("org-a")
    assert [v["version"] for v in versions] == [2, 1]


def test_in_memory_storage_isola_organizacoes():
    storage = InMemoryBrandingStorage()

    storage.save_version("org-a", _custom_payload("#111111"))
    storage.save_version("org-b", _custom_payload("#222222"))

    assert storage.load_latest("org-a")["payload"]["colors"]["primary_bg"] == "#111111"
    assert storage.load_latest("org-b")["payload"]["colors"]["primary_bg"] == "#222222"
    assert len(storage.list_versions("org-a")) == 1
    assert len(storage.list_versions("org-b")) == 1


def test_branding_service_persiste_entre_instancias_com_mesmo_storage():
    """The "restart" scenario: a fresh BrandingService, sharing only the
    storage backend (not the service object), still sees prior writes —
    proving persistence lives in the storage layer, not the service instance.
    """
    storage = InMemoryBrandingStorage()
    service1 = BrandingService(storage=storage)

    service1.set_theme("org-a", _theme_with_primary_bg("#ABCDEF"))

    service2 = BrandingService(storage=storage)
    theme = service2.get_theme("org-a")

    assert theme.colors.primary_bg == "#ABCDEF"


def test_branding_service_get_versions_retorna_historico():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    service.set_theme("org-a", _theme_with_primary_bg("#111111"))
    service.set_theme("org-a", _theme_with_primary_bg("#222222"))

    versions = service.get_versions("org-a")
    assert len(versions) == 2
    assert versions[0]["version"] == 2
    assert versions[1]["version"] == 1


def test_branding_service_registra_auditoria_ao_atualizar_tema():
    audit = PlatformAudit()
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage, audit=audit)

    service.set_theme("org-a", _theme_with_primary_bg("#111111"))

    events = [e for e in audit.get_events() if e["event"] == "branding_updated"]
    assert len(events) == 1
    assert events[0]["organization_id"] == "org-a"
    assert events[0]["metadata"]["version"] == 1


def test_branding_service_sem_audit_nao_quebra():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    service.set_theme("org-a", _theme_with_primary_bg("#111111"))

    assert service.get_theme("org-a").colors.primary_bg == "#111111"


def test_branding_service_sem_storage_usa_in_memory_por_padrao():
    service = BrandingService()

    assert isinstance(service._storage, InMemoryBrandingStorage)


def test_branding_service_organizacao_desconhecida_retorna_nexara_default():
    service = BrandingService()

    assert service.get_theme("org-ghost") == get_nexara_theme()


def test_branding_service_sem_organization_id_retorna_nexara_default():
    service = BrandingService()

    assert service.get_theme(None) == get_nexara_theme()


def test_postgres_branding_storage_cria_tabela():
    conn = MagicMock()
    cursor = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor

    with patch("app.platform.branding.branding_storage.psycopg2.connect", return_value=conn):
        PostgresBrandingStorage("postgresql://fake-dsn")

    calls = cursor.execute.call_args_list
    create_calls = [call for call in calls if "CREATE TABLE" in call.args[0]]
    assert len(create_calls) == 1
    assert "branding" in create_calls[0].args[0]


def test_postgres_branding_storage_save_version_retorna_versao_e_payload():
    conn = MagicMock()
    cursor = MagicMock()
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    cursor.fetchone.return_value = (1, ts)
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor

    with patch("app.platform.branding.branding_storage.psycopg2.connect", return_value=conn):
        storage = PostgresBrandingStorage("postgresql://fake-dsn")
        record = storage.save_version("org-a", {"colors": {}, "typography": {}, "spacing": {}})

    assert record["version"] == 1
    assert record["created_at"] == "2026-01-01T00:00:00+00:00"


def test_postgres_branding_storage_load_latest_sem_linha_retorna_none():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor

    with patch("app.platform.branding.branding_storage.psycopg2.connect", return_value=conn):
        storage = PostgresBrandingStorage("postgresql://fake-dsn")

        assert storage.load_latest("org-a") is None


def test_postgres_branding_storage_list_versions_mapeia_linhas():
    conn = MagicMock()
    cursor = MagicMock()
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    cursor.fetchall.return_value = [
        (2, {"colors": {}, "typography": {}, "spacing": {}}, ts),
        (1, {"colors": {}, "typography": {}, "spacing": {}}, ts),
    ]
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor

    with patch("app.platform.branding.branding_storage.psycopg2.connect", return_value=conn):
        storage = PostgresBrandingStorage("postgresql://fake-dsn")
        versions = storage.list_versions("org-a")

    assert [v["version"] for v in versions] == [2, 1]
