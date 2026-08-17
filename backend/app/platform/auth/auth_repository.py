from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.platform_auth import (
    PlatformOrganization,
    PlatformSession,
    PlatformUsage,
    PlatformUser,
    PlatformUserOrganization,
)


class AuthRepository:
    """Fase 1 — the real Postgres-backed persistence for `PlatformAuth`,
    used only when it is constructed with `repository=...` (see
    `platform_auth.py`). Synchronous on purpose: `PlatformAuth`'s public
    API has ~430 existing call sites, all synchronous, and Fase 1's
    explicit scope was to add real persistence without converting that
    whole call chain to async.

    Every method here returns/accepts plain dicts shaped exactly like the
    ones `PlatformAuth`'s in-memory mode already keeps in `self._users`/
    `self._organizations`/`self._sessions` today, so `PlatformAuth`'s own
    method bodies only need to change *which store* they read from, not
    their surrounding business logic (cache invalidation, audit logging,
    plan validation, ...) — that logic stays in `PlatformAuth` itself.

    Every method opens and closes its own short-lived session (no request-
    scoped session threaded through here): `PlatformAuth` has no notion of
    a request lifecycle today, and forcing one in would be a much bigger
    change than Fase 1's mandate.
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------

    def create_or_replace_user(
        self,
        email: str,
        salt: bytes,
        password_hash: bytes,
        role: str,
        permissions: list[str],
        organization_id: str | None,
        organization_role: str,
    ) -> None:
        """Upsert by email — mirrors dict-mode's own `self._users[email] =
        {...}` full overwrite (`register_user()` re-registering an
        existing email today just replaces the whole record)."""
        with self._session_factory() as session:
            user = session.get(PlatformUser, email)

            if user is None:
                user = PlatformUser(email=email)
                session.add(user)

            user.password_salt = salt
            user.password_hash = password_hash
            user.role = role
            user.permissions = list(permissions)
            user.organization_id = organization_id
            user.organization_role = organization_role

            session.commit()

    def get_user(self, email: str) -> dict | None:
        with self._session_factory() as session:
            user = session.get(PlatformUser, email)

            if user is None:
                return None

            return self._user_to_dict(user)

    def user_exists(self, email: str) -> bool:
        with self._session_factory() as session:
            return session.get(PlatformUser, email) is not None

    def has_any_admin(self) -> bool:
        with self._session_factory() as session:
            stmt = select(PlatformUser.email).where(PlatformUser.role == "admin").limit(1)
            return session.execute(stmt).first() is not None

    def set_user_fields(self, email: str, **fields) -> bool:
        """Generic field patch, used by the explicit test-support setters
        on PlatformAuth (`set_user_role_for_test`, ...). Returns False if
        the user doesn't exist."""
        with self._session_factory() as session:
            user = session.get(PlatformUser, email)

            if user is None:
                return False

            for key, value in fields.items():
                setattr(user, key, value)

            session.commit()
            return True

    @staticmethod
    def _user_to_dict(user: PlatformUser) -> dict:
        return {
            "salt": bytes(user.password_salt),
            "hash": bytes(user.password_hash),
            "role": user.role,
            "permissions": list(user.permissions or []),
            "organization_id": user.organization_id,
            "organization_role": user.organization_role,
        }

    # ------------------------------------------------------------------
    # organizations
    # ------------------------------------------------------------------

    def create_organization(self, org_id: str, name: str) -> None:
        with self._session_factory() as session:
            session.add(PlatformOrganization(id=org_id, name=name))
            session.commit()

    def get_organization(self, org_id: str) -> dict | None:
        with self._session_factory() as session:
            org = session.get(PlatformOrganization, org_id)

            if org is None:
                return None

            member_emails = self._member_emails(session, org_id)
            return self._org_to_dict(org, member_emails)

    def list_organizations(self) -> dict[str, dict]:
        with self._session_factory() as session:
            orgs = session.execute(select(PlatformOrganization)).scalars().all()
            memberships = session.execute(select(PlatformUserOrganization)).scalars().all()

            members_by_org: dict[str, list[str]] = {}
            for membership in memberships:
                members_by_org.setdefault(membership.organization_id, []).append(
                    membership.user_email
                )

            return {
                org.id: self._org_to_dict(org, members_by_org.get(org.id, [])) for org in orgs
            }

    def find_organization_by_stripe_customer(self, customer_id: str) -> str | None:
        with self._session_factory() as session:
            stmt = select(PlatformOrganization.id).where(
                PlatformOrganization.stripe_customer_id == customer_id
            )
            row = session.execute(stmt).first()
            return row[0] if row is not None else None

    def update_organization(self, org_id: str, **fields) -> bool:
        """Generic field patch — used for plan changes, retention flags,
        lead states, renames, Stripe ids, subscription status and the
        `set_organization_created_at` test-support hook. Returns False if
        the organization doesn't exist; raising `LookupError` in that case
        is `PlatformAuth`'s job (matches dict-mode's own convention)."""
        with self._session_factory() as session:
            org = session.get(PlatformOrganization, org_id)

            if org is None:
                return False

            for key, value in fields.items():
                setattr(org, key, value)

            session.commit()
            return True

    def add_membership(self, email: str, org_id: str, role: str = "member") -> bool:
        """Returns True if a new membership row was inserted, False if the
        user was already a member — mirrors dict-mode's own `if email not
        in org["users"]` guard in `add_user_to_organization()`."""
        with self._session_factory() as session:
            existing = session.get(PlatformUserOrganization, (email, org_id))

            if existing is not None:
                return False

            session.add(
                PlatformUserOrganization(user_email=email, organization_id=org_id, role=role)
            )
            session.commit()
            return True

    @staticmethod
    def _member_emails(session: Session, org_id: str) -> list[str]:
        stmt = (
            select(PlatformUserOrganization.user_email)
            .where(PlatformUserOrganization.organization_id == org_id)
            .order_by(PlatformUserOrganization.created_at)
        )
        return [row[0] for row in session.execute(stmt).all()]

    @staticmethod
    def _org_to_dict(org: PlatformOrganization, member_emails: list[str]) -> dict:
        """Omits keys the org never had a value set for (`plan_history`,
        `retention_flag`, ...) rather than exposing the JSONB/boolean
        column defaults — dict-mode never had these keys at all until the
        corresponding setter ran at least once (see e.g.
        `test_set_organization_plan_invalido_nao_registra_historico`,
        which asserts `"plan_history" not in ...` for an org that never
        had a successful plan change), and callers throughout
        `platform_auth.py` already use `.get(key, default)` for all of
        these, so omission and an explicit default are equivalent to them.
        """
        result: dict = {
            "name": org.name,
            "created_at": int(org.created_at.timestamp()),
            "users": member_emails,
            "plan": org.plan,
        }

        if org.plan_history:
            result["plan_history"] = list(org.plan_history)

        if org.retention_flag:
            result["retention_flag"] = org.retention_flag

        if org.lead_states:
            result["lead_states"] = dict(org.lead_states)

        if org.stripe_customer_id is not None:
            result["stripe_customer_id"] = org.stripe_customer_id

        if org.stripe_subscription_id is not None:
            result["stripe_subscription_id"] = org.stripe_subscription_id

        if org.subscription_status is not None:
            result["subscription_status"] = org.subscription_status

        if org.canceled_at is not None:
            result["canceled_at"] = int(org.canceled_at.timestamp())

        return result

    # ------------------------------------------------------------------
    # sessions
    # ------------------------------------------------------------------

    def create_session(
        self,
        token: str,
        email: str,
        organization_id: str | None,
        role: str | None,
        permissions: list[str],
        issued_at: int,
        ttl_seconds: int,
    ) -> None:
        """`expires_at` is informational only (e.g. for a future cleanup
        job) — actual expiry is decided by `PlatformAuth.get_session()`
        recomputing `issued_at + self._ttl` at read time, exactly like
        dict-mode, so a `PlatformAuth` instance's own `session_ttl` always
        governs even if it differs from the value passed here."""
        issued_at_dt = datetime.fromtimestamp(issued_at, tz=timezone.utc)

        with self._session_factory() as session:
            session.add(
                PlatformSession(
                    token=token,
                    user_email=email,
                    organization_id=organization_id,
                    role=role,
                    permissions=list(permissions),
                    issued_at=issued_at_dt,
                    expires_at=issued_at_dt + timedelta(seconds=ttl_seconds),
                )
            )
            session.commit()

    def get_session(self, token: str) -> dict | None:
        with self._session_factory() as session:
            row = session.get(PlatformSession, token)

            if row is None:
                return None

            return self._session_to_dict(row)

    def delete_session(self, token: str) -> dict | None:
        """Deletes and returns the session that was deleted (or None) —
        mirrors dict-mode's own `self._sessions.pop(token, None)` in
        `logout()`, which needs the just-deleted session's email/org for
        its audit log entry."""
        with self._session_factory() as session:
            row = session.get(PlatformSession, token)

            if row is None:
                return None

            data = self._session_to_dict(row)
            session.delete(row)
            session.commit()
            return data

    @staticmethod
    def _session_to_dict(row: PlatformSession) -> dict:
        return {
            "email": row.user_email,
            "issued_at": int(row.issued_at.timestamp()),
            "organization_id": row.organization_id,
            "role": row.role,
            "permissions": list(row.permissions or []),
        }

    # ------------------------------------------------------------------
    # usage
    # ------------------------------------------------------------------

    def get_usage(self, org_id: str, today: date) -> int:
        with self._session_factory() as session:
            row = session.get(PlatformUsage, (org_id, today))
            return row.requests_today if row is not None else 0

    def increment_usage(self, org_id: str, today: date) -> int:
        with self._session_factory() as session:
            row = session.get(PlatformUsage, (org_id, today))

            if row is None:
                row = PlatformUsage(organization_id=org_id, usage_date=today, requests_today=0)
                session.add(row)

            row.requests_today += 1
            session.commit()
            return row.requests_today

    def clear_usage(self, org_id: str, today: date) -> None:
        """Test-support: deletes today's usage row (if any), so the next
        read/increment starts a fresh bucket at 0 — the repo-mode
        equivalent of dict-mode backdating `last_reset` by a day. Real day
        rollovers need no such call: a new calendar date is already a new
        primary key, so it starts at 0 on its own."""
        with self._session_factory() as session:
            row = session.get(PlatformUsage, (org_id, today))

            if row is not None:
                session.delete(row)
                session.commit()
