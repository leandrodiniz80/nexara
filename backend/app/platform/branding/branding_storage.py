from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import Json


class BrandingStorage:
    """A dedicated, pluggable persistence layer for versioned branding — kept
    separate from `PlatformStorage` deliberately: that interface's `load()`/
    `save()` replace one whole blob per call, which is exactly right for
    `PlatformAuth`'s single-document model but wrong here (branding needs
    per-organization version history, not one shared document that a second
    write would silently clobber).
    """

    def save_version(self, organization_id: str, payload: dict) -> dict:
        raise NotImplementedError

    def load_latest(self, organization_id: str) -> dict | None:
        return None

    def list_versions(self, organization_id: str) -> list[dict]:
        return []


class InMemoryBrandingStorage(BrandingStorage):
    def __init__(self):
        self._versions: dict[str, list[dict]] = {}

    def save_version(self, organization_id: str, payload: dict) -> dict:
        history = self._versions.setdefault(organization_id, [])
        record = {
            "version": len(history) + 1,
            "payload": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        history.append(record)

        return record

    def load_latest(self, organization_id: str) -> dict | None:
        history = self._versions.get(organization_id)

        if not history:
            return None

        return history[-1]

    def list_versions(self, organization_id: str) -> list[dict]:
        return list(reversed(self._versions.get(organization_id, [])))


class PostgresBrandingStorage(BrandingStorage):
    """Its own table (`branding`), independent of `platform_data` — so it can
    never collide with `PlatformAuth`'s or `PlatformAudit`'s data even when
    pointed at the same database.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn
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
                        CREATE TABLE IF NOT EXISTS branding (
                            id SERIAL PRIMARY KEY,
                            organization_id TEXT NOT NULL,
                            version INTEGER NOT NULL,
                            payload JSONB NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
        finally:
            conn.close()

    def save_version(self, organization_id: str, payload: dict) -> dict:
        conn = self._connect()

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO branding (organization_id, version, payload)
                        VALUES (
                            %s,
                            COALESCE(
                                (SELECT MAX(version) FROM branding WHERE organization_id = %s),
                                0
                            ) + 1,
                            %s
                        )
                        RETURNING version, created_at
                        """,
                        (organization_id, organization_id, Json(payload)),
                    )
                    version, created_at = cur.fetchone()
        finally:
            conn.close()

        return {"version": version, "payload": payload, "created_at": created_at.isoformat()}

    def load_latest(self, organization_id: str) -> dict | None:
        conn = self._connect()

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT version, payload, created_at
                        FROM branding
                        WHERE organization_id = %s
                        ORDER BY version DESC
                        LIMIT 1
                        """,
                        (organization_id,),
                    )
                    row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        version, payload, created_at = row

        return {"version": version, "payload": payload, "created_at": created_at.isoformat()}

    def list_versions(self, organization_id: str) -> list[dict]:
        conn = self._connect()

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT version, payload, created_at
                        FROM branding
                        WHERE organization_id = %s
                        ORDER BY version DESC
                        """,
                        (organization_id,),
                    )
                    rows = cur.fetchall()
        finally:
            conn.close()

        return [
            {"version": version, "payload": payload, "created_at": created_at.isoformat()}
            for version, payload, created_at in rows
        ]
