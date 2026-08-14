import psycopg2
from psycopg2.extras import Json

from app.platform.storage.platform_storage import PlatformStorage, _decode_bytes, _encode_bytes


class PostgresStorage(PlatformStorage):
    """Backward-compatible with the single-tenant Sprint 217 shape: with no
    `organization_id`, every operation targets the original `id = 1` row, byte
    for byte the same SQL as before. Passing `organization_id` scopes reads/writes
    to a row keyed by that tenant instead — still one shared table (`mesmo que
    ainda não use tabela separada`), a foundation for a future per-tenant schema
    or Postgres row-level security, not that migration itself.

    Known limitation of this foundation: allocating a fresh row id for a new
    tenant via `SELECT COALESCE(MAX(id), 0) + 1` has a benign race under truly
    concurrent first-writes for two different brand-new tenants — acceptable here
    since this step is explicitly preparatory, not the final multi-tenant storage
    design.
    """

    def __init__(self, dsn: str, organization_id: str | None = None):
        self._dsn = dsn
        self._organization_id = organization_id
        self._init_db()

    def _connect(self):
        return psycopg2.connect(self._dsn)

    def _init_db(self) -> None:
        conn = self._connect()

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS platform_data (
                            id INTEGER PRIMARY KEY,
                            payload JSONB NOT NULL
                        )
                        """
                    )
                    cur.execute(
                        "ALTER TABLE platform_data ADD COLUMN IF NOT EXISTS organization_id TEXT"
                    )
        finally:
            conn.close()

    def load(self) -> dict:
        conn = self._connect()

        try:
            with conn:
                with conn.cursor() as cur:
                    if self._organization_id is None:
                        cur.execute("SELECT payload FROM platform_data WHERE id = 1")
                    else:
                        cur.execute(
                            "SELECT payload FROM platform_data WHERE organization_id = %s",
                            (self._organization_id,),
                        )
                    row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            return {}

        return _decode_bytes(row[0])

    def save(self, data: dict) -> None:
        encoded = _encode_bytes(data)

        conn = self._connect()

        try:
            with conn:
                with conn.cursor() as cur:
                    if self._organization_id is None:
                        cur.execute(
                            """
                            INSERT INTO platform_data (id, payload)
                            VALUES (1, %s)
                            ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload
                            """,
                            (Json(encoded),),
                        )
                    else:
                        self._save_for_tenant(cur, encoded)
        finally:
            conn.close()

    def _save_for_tenant(self, cur, encoded: dict) -> None:
        cur.execute(
            "SELECT id FROM platform_data WHERE organization_id = %s",
            (self._organization_id,),
        )
        row = cur.fetchone()

        if row is not None:
            cur.execute(
                "UPDATE platform_data SET payload = %s WHERE id = %s",
                (Json(encoded), row[0]),
            )
            return

        cur.execute(
            """
            INSERT INTO platform_data (id, organization_id, payload)
            VALUES ((SELECT COALESCE(MAX(id), 0) + 1 FROM platform_data), %s, %s)
            """,
            (self._organization_id, Json(encoded)),
        )
