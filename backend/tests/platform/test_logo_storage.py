from app.platform.audit.platform_audit import PlatformAudit
from app.platform.branding.branding_service import BrandingService
from app.platform.branding.logo_storage import InMemoryLogoStorage, LogoStorage


def test_logo_storage_base_get_logo_retorna_none():
    storage = LogoStorage()

    assert storage.get_logo("org-a") is None


def test_logo_storage_base_save_logo_e_no_op():
    storage = LogoStorage()

    storage.save_logo("org-a", b"bytes", "image/png")

    assert storage.get_logo("org-a") is None


def test_in_memory_save_e_get_logo_round_trip():
    storage = InMemoryLogoStorage()

    storage.save_logo("org-a", b"png-bytes", "image/png")

    assert storage.get_logo("org-a") == (b"png-bytes", "image/png")


def test_in_memory_get_logo_organizacao_desconhecida_retorna_none():
    storage = InMemoryLogoStorage()

    assert storage.get_logo("org-ghost") is None


def test_in_memory_isolado_entre_organizacoes():
    storage = InMemoryLogoStorage()

    storage.save_logo("org-a", b"logo-a", "image/png")
    storage.save_logo("org-b", b"logo-b", "image/jpeg")

    assert storage.get_logo("org-a") == (b"logo-a", "image/png")
    assert storage.get_logo("org-b") == (b"logo-b", "image/jpeg")


def test_in_memory_save_logo_sobrescreve_versao_anterior():
    storage = InMemoryLogoStorage()

    storage.save_logo("org-a", b"old-logo", "image/png")
    storage.save_logo("org-a", b"new-logo", "image/webp")

    assert storage.get_logo("org-a") == (b"new-logo", "image/webp")


def test_branding_service_set_logo_depois_get_logo():
    service = BrandingService()

    service.set_logo("org-a", b"logo-bytes", "image/png")

    assert service.get_logo("org-a") == (b"logo-bytes", "image/png")


def test_branding_service_get_logo_sem_upload_retorna_none():
    service = BrandingService()

    assert service.get_logo("org-a") is None


def test_branding_service_has_logo_true_apos_set_logo():
    service = BrandingService()

    service.set_logo("org-a", b"logo-bytes", "image/png")

    assert service.has_logo("org-a") is True


def test_branding_service_has_logo_false_sem_upload():
    service = BrandingService()

    assert service.has_logo("org-a") is False


def test_branding_service_has_logo_false_para_organization_id_none():
    service = BrandingService()

    assert service.has_logo(None) is False


def test_branding_service_set_logo_isolado_entre_organizacoes():
    service = BrandingService()

    service.set_logo("org-a", b"logo-a", "image/png")

    assert service.has_logo("org-b") is False
    assert service.get_logo("org-b") is None


def test_branding_service_set_logo_gera_evento_de_auditoria():
    audit = PlatformAudit()
    service = BrandingService(audit=audit)

    service.set_logo("org-a", b"logo-bytes", "image/png")

    events = [e for e in audit.get_events() if e["event"] == "logo_updated"]
    assert len(events) == 1
    assert events[0]["organization_id"] == "org-a"
    assert events[0]["metadata"]["content_type"] == "image/png"
