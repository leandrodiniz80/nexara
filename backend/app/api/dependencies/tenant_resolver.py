from fastapi import Depends, Request


class DomainTenantResolver:
    """Simple in-memory domain -> organization_id map for now (evolves to a
    DB-backed lookup later, per Sprint 234's own preview). Wrapped in a class
    — rather than bare module-level functions mutating a bare module-level
    dict — specifically so it can be swapped per test via
    `app.dependency_overrides`, the same way every other pluggable service in
    this platform is; a bare global dict has no such override point and would
    leak domain registrations across the whole test session.
    """

    def __init__(self) -> None:
        self._domain_map: dict[str, str] = {}

    def register_domain(self, domain: str, organization_id: str) -> None:
        self._domain_map[domain.lower()] = organization_id

    def get_owner(self, domain: str) -> str | None:
        """Exact-match lookup (no port-stripping, no host-header normalization
        beyond lowercasing) — used by the registration endpoint to detect
        domain takeover attempts before writing, distinct from `resolve()`
        which is the request-time, Host-header-driven lookup.
        """
        return self._domain_map.get(domain.lower())

    def resolve(self, host: str) -> str | None:
        return self._domain_map.get(host.split(":")[0].lower())

    def get_domains_for_organization(self, organization_id: str) -> list[str]:
        """Reverse lookup — used to scope the metrics dashboard (Sprint 248)
        to exactly the domains a tenant owns, instead of ranking across the
        whole platform and filtering after the fact (which would silently
        drop a tenant's own low-traffic domain if it happened to fall
        outside some global top-N cutoff)."""
        return [
            domain
            for domain, owner_id in self._domain_map.items()
            if owner_id == organization_id
        ]

    def get_all_domains(self) -> list[str]:
        """Every registered domain, regardless of owner — used only for the
        `role == "admin"` platform-wide view (Sprint 254); every other
        caller goes through `get_domains_for_organization()` instead."""
        return list(self._domain_map.keys())


_domain_resolver: DomainTenantResolver | None = None


def get_domain_tenant_resolver() -> DomainTenantResolver:
    global _domain_resolver

    if _domain_resolver is None:
        _domain_resolver = DomainTenantResolver()

    return _domain_resolver


def get_tenant_id_from_domain(
    request: Request,
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
) -> str | None:
    host = request.headers.get("host", "")

    return resolver.resolve(host)
