"""Tests for ApiKeyManager (Sprint 266, hardened in Sprint 267).

Real bug in the Sprint 266 spec, fixed there — see api_key_manager.py's
own docstring: `revoke_key()` deleted the key unconditionally, with no
check that it actually belonged to the calling tenant. Any authenticated
tenant could revoke *any other tenant's* API key just by knowing its
value — a real, exploitable denial-of-service against another customer's
live integration.

Sprint 267 changed `list_keys()`'s return shape from `list[str]` (raw
key values) to `list[dict]` (`{"key": masked, "created_at": ...}`) — a
deliberate, expected part of that sprint's own goal (never expose a full
key again once it's been listed). Assertions here that used to compare
against raw key strings now compare against masked values via
`mask_api_key()`. See test_api_key_security.py for the hashing/masking-
specific coverage this sprint added.
"""

from app.platform.tenant.api_key_manager import ApiKeyManager, mask_api_key


class _FakeClient:
    def __init__(self):
        self._strings: dict[str, str] = {}
        self._sets: dict[str, set] = {}
        self._hashes: dict[str, dict] = {}

    def get(self, key):
        return self._strings.get(key)

    def set(self, key, value):
        self._strings[key] = value

    def delete(self, key):
        self._strings.pop(key, None)
        self._hashes.pop(key, None)

    def sadd(self, key, value):
        self._sets.setdefault(key, set()).add(value)

    def srem(self, key, value):
        self._sets.get(key, set()).discard(value)

    def smembers(self, key):
        return set(self._sets.get(key, set()))

    def hset(self, key, mapping):
        self._hashes.setdefault(key, {}).update(mapping)

    def hgetall(self, key):
        return dict(self._hashes.get(key, {}))


def test_generate_key_tem_prefixo_ak():
    manager = ApiKeyManager(_FakeClient())

    key = manager.generate_key("tenant-a")

    assert key.startswith("ak_")


def test_generate_key_e_mapeada_para_o_tenant_correto():
    manager = ApiKeyManager(_FakeClient())

    key = manager.generate_key("tenant-a")

    assert manager.get_tenant(key) == "tenant-a"


def test_get_tenant_de_key_inexistente_retorna_none():
    manager = ApiKeyManager(_FakeClient())

    assert manager.get_tenant("ak_does_not_exist") is None


def test_generate_key_gera_valores_unicos():
    manager = ApiKeyManager(_FakeClient())

    key_a = manager.generate_key("tenant-a")
    key_b = manager.generate_key("tenant-a")

    assert key_a != key_b


def test_list_keys_vazio_por_padrao():
    manager = ApiKeyManager(_FakeClient())

    assert manager.list_keys("tenant-a") == []


def test_list_keys_retorna_todas_as_keys_do_tenant_mascaradas():
    manager = ApiKeyManager(_FakeClient())
    key_a = manager.generate_key("tenant-a")
    key_b = manager.generate_key("tenant-a")

    keys = manager.list_keys("tenant-a")

    masked_values = {item["key"] for item in keys}
    assert masked_values == {mask_api_key(key_a), mask_api_key(key_b)}


def test_list_keys_e_isolado_por_tenant():
    manager = ApiKeyManager(_FakeClient())
    key_a = manager.generate_key("tenant-a")
    manager.generate_key("tenant-b")

    keys_a = manager.list_keys("tenant-a")

    assert len(keys_a) == 1
    assert keys_a[0]["key"] == mask_api_key(key_a)


def test_revoke_key_remove_a_key_do_proprio_tenant():
    manager = ApiKeyManager(_FakeClient())
    key = manager.generate_key("tenant-a")

    revoked = manager.revoke_key("tenant-a", key)

    assert revoked is True
    assert manager.get_tenant(key) is None
    assert manager.list_keys("tenant-a") == []


def test_revoke_key_de_outro_tenant_e_bloqueada():
    """The core security fix: tenant-b must not be able to revoke
    tenant-a's key just by knowing its value."""
    manager = ApiKeyManager(_FakeClient())
    key_a = manager.generate_key("tenant-a")

    revoked = manager.revoke_key("tenant-b", key_a)

    assert revoked is False
    # The key must still be fully intact and usable.
    assert manager.get_tenant(key_a) == "tenant-a"
    assert len(manager.list_keys("tenant-a")) == 1
    assert manager.list_keys("tenant-a")[0]["key"] == mask_api_key(key_a)


def test_revoke_key_inexistente_retorna_false():
    manager = ApiKeyManager(_FakeClient())

    assert manager.revoke_key("tenant-a", "ak_does_not_exist") is False


def test_revoke_key_nao_afeta_outras_keys_do_mesmo_tenant():
    manager = ApiKeyManager(_FakeClient())
    key_a = manager.generate_key("tenant-a")
    key_b = manager.generate_key("tenant-a")

    manager.revoke_key("tenant-a", key_a)

    remaining = manager.list_keys("tenant-a")
    assert len(remaining) == 1
    assert remaining[0]["key"] == mask_api_key(key_b)
