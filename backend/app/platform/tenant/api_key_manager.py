import hashlib
import secrets
from datetime import datetime, timezone


def hash_api_key(key: str) -> str:
    """Module-level, not a private method — the router (Sprint 267's
    audit logging) and `ApiRateLimiter`'s caller both need to derive the
    same hash a raw key produces, without reaching into `ApiKeyManager`'s
    own internals to do it.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def mask_api_key(key: str) -> str:
    """`ak_XXX...YYYY` — enough to let a human recognize which key is
    which in a list or an audit trail, never enough to reconstruct or use
    the real value."""
    return f"{key[:6]}...{key[-4:]}"


class ApiKeyManager:
    """Machine-to-machine credentials for a tenant (Sprint 266, hardened
    in Sprint 267) — a key maps to exactly one `tenant_id`, with a
    reverse per-tenant index (`tenant:keys:{tenant_id}`, a Redis set) for
    listing/revocation without a keyspace scan.

    Sprint 267: the raw key is *never* persisted anywhere, in any form —
    not as a value, not as part of a key name. Only `sha256(key)` is
    stored (as the Redis key suffix for the tenant-mapping and metadata
    entries) and only that hash is ever looked up against. The raw value
    exists only transiently, in the response to whoever just generated
    it — the one and only time it's ever shown in full.

    No separate `hmac.compare_digest()` call, despite the spec's own
    explicit mention of it: that guards against *timing attacks on a
    direct secret-vs-secret comparison* (e.g. a naive byte-by-byte loop
    letting an attacker infer a secret's bytes one at a time from
    response-time differences). Nothing here does that kind of
    comparison — `get_tenant()` hashes the candidate key and performs a
    single O(1) hash-table lookup (Redis `GET`, or the in-memory
    fallback's `dict.get()`), which doesn't leak partial-match
    information through timing the way a linear compare would. Using
    `hmac.compare_digest()` here would have nothing real to guard.

    Duck-typed `client` (Redis, or the in-memory fallback in
    `app/api/dependencies/api_keys.py`) needs `get`/`set`/`delete`/
    `sadd`/`srem`/`smembers`/`hset`/`hgetall`.
    """

    _KEY_PREFIX = "ak_"

    def __init__(self, client):
        self._client = client

    def _key_entry(self, key_hash: str) -> str:
        return f"apikey:{key_hash}"

    def _key_meta(self, key_hash: str) -> str:
        return f"apikey:meta:{key_hash}"

    def _tenant_keys(self, tenant_id: str) -> str:
        # Unchanged from Sprint 266 (`tenant:keys:{tenant_id}`, not the
        # spec's own `tenant:{tenant_id}:keys`) — purely a naming
        # convention with no functional difference either way, but
        # switching it would silently orphan any tenant-key index written
        # under the old format, contradicting this sprint's own "100%
        # compatível com Sprint 266" requirement for no real benefit.
        return f"tenant:keys:{tenant_id}"

    def generate_key(self, tenant_id: str) -> str:
        """Still returns the full, raw key — unchanged contract from
        Sprint 266, per this sprint's own explicit "don't change the
        creation response contract" rule. Only what gets *persisted*
        changes: the hash (for lookup), never the raw value.
        """
        key = f"{self._KEY_PREFIX}{secrets.token_hex(16)}"
        key_hash = hash_api_key(key)

        self._client.set(self._key_entry(key_hash), tenant_id)
        self._client.sadd(self._tenant_keys(tenant_id), key_hash)
        self._client.hset(
            self._key_meta(key_hash),
            mapping={
                "masked": mask_api_key(key),
                # datetime.now(timezone.utc), not datetime.utcnow() (the
                # spec's own version) — utcnow() is deprecated as of
                # Python 3.12 and inconsistent with every other timestamp
                # in this codebase (PlatformAudit.log_event() and every
                # sprint since).
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return key

    def get_tenant(self, key: str) -> str | None:
        return self._client.get(self._key_entry(hash_api_key(key)))

    def revoke_key(self, tenant_id: str, key: str) -> bool:
        """`True` only if `key` actually belongs to `tenant_id` — the
        ownership check from Sprint 266's own fix, preserved here (the
        spec's Sprint 267 code correctly kept it this time). Also deletes
        the metadata entry (`apikey:meta:{hash}`) alongside the mapping
        and reverse-index entries — the spec's own version left it
        behind, a permanent, ever-growing Redis leak: every revoked key
        would still have its masked value and creation timestamp sitting
        in Redis forever, unreachable from `list_keys()` but never
        cleaned up either.
        """
        key_hash = hash_api_key(key)

        if self._client.get(self._key_entry(key_hash)) != tenant_id:
            return False

        self._client.delete(self._key_entry(key_hash))
        self._client.delete(self._key_meta(key_hash))
        self._client.srem(self._tenant_keys(tenant_id), key_hash)

        return True

    def list_keys(self, tenant_id: str) -> list[dict]:
        """Masked values + creation timestamps, never the raw key (which
        isn't stored anywhere to return even if this wanted to) — sorted
        by `created_at`, not left in whatever order `smembers()`'s
        underlying Redis/Python set happens to iterate in (the same
        "never dependent on set iteration order" care already taken
        elsewhere in this platform, e.g. Sprint 260's digest domains).

        A known, deliberate limitation, not fixed here: a key can only be
        revoked by its full raw value (see `revoke_key()`) — if a caller
        loses that value after creation, this masked listing alone can't
        identify it precisely enough to revoke by itself. A stable
        internal key id, separate from the secret, would fix this; not
        added here since the spec's own requested shape
        (`{"key": masked, "created_at": ...}`) doesn't include one, and
        adding an id-based revocation path wasn't asked for.
        """
        hashes = self._client.smembers(self._tenant_keys(tenant_id))

        items = []
        for key_hash in hashes:
            meta = self._client.hgetall(self._key_meta(key_hash))
            items.append({"key": meta.get("masked"), "created_at": meta.get("created_at")})

        items.sort(key=lambda item: item.get("created_at") or "")

        return items
