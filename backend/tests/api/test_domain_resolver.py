from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver


def test_resolve_dominio_registrado():
    resolver = DomainTenantResolver()

    resolver.register_domain("cliente.com", "org-a")

    assert resolver.resolve("cliente.com") == "org-a"


def test_resolve_dominio_desconhecido_retorna_none():
    resolver = DomainTenantResolver()

    assert resolver.resolve("unknown.com") is None


def test_resolve_normaliza_porta_e_maiusculas():
    resolver = DomainTenantResolver()

    resolver.register_domain("Cliente.com", "org-a")

    assert resolver.resolve("cliente.com:8443") == "org-a"


def test_get_owner_dominio_registrado():
    resolver = DomainTenantResolver()

    resolver.register_domain("cliente.com", "org-a")

    assert resolver.get_owner("cliente.com") == "org-a"


def test_get_owner_dominio_nao_registrado_retorna_none():
    resolver = DomainTenantResolver()

    assert resolver.get_owner("cliente.com") is None


def test_get_owner_e_case_insensitive():
    resolver = DomainTenantResolver()

    resolver.register_domain("Cliente.com", "org-a")

    assert resolver.get_owner("cliente.com") == "org-a"


def test_register_domain_sobrescreve_dono_anterior():
    resolver = DomainTenantResolver()

    resolver.register_domain("cliente.com", "org-a")
    resolver.register_domain("cliente.com", "org-b")

    assert resolver.get_owner("cliente.com") == "org-b"


def test_instancias_isoladas_entre_si():
    resolver_a = DomainTenantResolver()
    resolver_b = DomainTenantResolver()

    resolver_a.register_domain("cliente.com", "org-a")

    assert resolver_b.get_owner("cliente.com") is None


def test_get_domain_tenant_resolver_retorna_singleton():
    first = get_domain_tenant_resolver()
    second = get_domain_tenant_resolver()

    assert first is second
