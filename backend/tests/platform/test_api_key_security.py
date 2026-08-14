"""Dedicated security-hardening tests for ApiKeyManager (Sprint 267):
hash storage, masking, and that revoke/list behave correctly under the
new hashed-storage scheme. See test_api_key_manager.py for the general
behavioral coverage (isolation, uniqueness, ...) carried over from
Sprint 266.
"""

import hashlib

from app.platform.tenant.api_key_manager import ApiKeyManager, hash_api_key, mask_api_key


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


# --- hash_api_key()/mask_api_key() (pure functions) ------------------------


def test_hash_api_key_e_sha256_hexdigest():
    key = "ak_" + "a" * 32

    assert hash_api_key(key) == hashlib.sha256(key.encode()).hexdigest()


def test_hash_api_key_e_deterministico():
    key = "ak_" + "b" * 32

    assert hash_api_key(key) == hash_api_key(key)


def test_hash_api_key_dominios_diferentes_geram_hashes_diferentes():
    assert hash_api_key("ak_" + "a" * 32) != hash_api_key("ak_" + "b" * 32)


def test_mask_api_key_mostra_apenas_prefixo_e_sufixo():
    key = "ak_1234567890abcdef1234567890abcd"

    masked = mask_api_key(key)

    assert masked == "ak_123...abcd"
    assert key not in masked


# --- plaintext never persisted ------------------------------------------


def test_generate_key_nao_armazena_a_chave_em_texto_puro():
    """The core Sprint 267 guarantee: nothing written to the client's
    backing storage ever contains the raw key value — only its hash."""
    client = _FakeClient()
    manager = ApiKeyManager(client)

    key = manager.generate_key("tenant-a")

    for stored_value in client._strings.values():
        assert stored_value != key
        assert key not in stored_value

    for stored_set in client._sets.values():
        assert key not in stored_set

    for stored_hash in client._hashes.values():
        for value in stored_hash.values():
            assert value != key
            assert key not in value


def test_generate_key_armazena_apenas_o_hash_como_chave_de_lookup():
    client = _FakeClient()
    manager = ApiKeyManager(client)

    key = manager.generate_key("tenant-a")

    assert f"apikey:{hash_api_key(key)}" in client._strings
    assert f"apikey:{key}" not in client._strings


def test_get_tenant_funciona_via_hash_lookup():
    manager = ApiKeyManager(_FakeClient())
    key = manager.generate_key("tenant-a")

    assert manager.get_tenant(key) == "tenant-a"


def test_get_tenant_de_valor_arbitrario_nao_reconhecido_retorna_none():
    manager = ApiKeyManager(_FakeClient())
    manager.generate_key("tenant-a")

    assert manager.get_tenant("ak_" + "0" * 32) is None


# --- masked metadata -------------------------------------------------------


def test_generate_key_grava_metadata_mascarada_e_created_at():
    client = _FakeClient()
    manager = ApiKeyManager(client)

    key = manager.generate_key("tenant-a")

    meta = client.hgetall(f"apikey:meta:{hash_api_key(key)}")
    assert meta["masked"] == mask_api_key(key)
    assert meta["created_at"]


def test_list_keys_retorna_apenas_valores_mascarados():
    manager = ApiKeyManager(_FakeClient())
    key = manager.generate_key("tenant-a")

    items = manager.list_keys("tenant-a")

    assert items[0]["key"] == mask_api_key(key)
    assert key not in items[0]["key"]


def test_list_keys_inclui_created_at():
    manager = ApiKeyManager(_FakeClient())
    manager.generate_key("tenant-a")

    items = manager.list_keys("tenant-a")

    assert items[0]["created_at"]


def test_list_keys_ordenado_por_created_at():
    manager = ApiKeyManager(_FakeClient())
    key_a = manager.generate_key("tenant-a")
    key_b = manager.generate_key("tenant-a")

    items = manager.list_keys("tenant-a")

    assert [item["key"] for item in items] == [mask_api_key(key_a), mask_api_key(key_b)]


# --- revoke respects tenant + cleans up metadata ----------------------------


def test_revoke_key_respeita_tenant():
    manager = ApiKeyManager(_FakeClient())
    key = manager.generate_key("tenant-a")

    assert manager.revoke_key("tenant-b", key) is False
    assert manager.revoke_key("tenant-a", key) is True


def test_revoke_key_remove_a_metadata_tambem():
    """The spec's own version left `apikey:meta:{hash}` behind forever
    after a revoke — a permanent Redis leak. Confirms it's actually
    cleaned up."""
    client = _FakeClient()
    manager = ApiKeyManager(client)
    key = manager.generate_key("tenant-a")
    key_hash = hash_api_key(key)

    manager.revoke_key("tenant-a", key)

    assert client.hgetall(f"apikey:meta:{key_hash}") == {}
