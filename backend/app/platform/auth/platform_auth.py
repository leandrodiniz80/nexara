import hashlib
import hmac
import os
import time
import uuid
from datetime import datetime, timezone

from app.platform.audit.platform_audit import PlatformAudit
from app.platform.auth.auth_repository import AuthRepository
from app.platform.cache.platform_cache import PlatformCache
from app.platform.logging.platform_logger import PlatformLogger
from app.platform.metrics.platform_metrics import PlatformMetrics
from app.platform.rate_limit.platform_rate_limiter import PlatformRateLimiter, RateLimitExceeded
from app.platform.storage.platform_storage import InMemoryStorage, PlatformStorage

_PBKDF2_ITERATIONS = 200_000
_DEFAULT_SESSION_TTL = 3600
_SECONDS_PER_DAY = 86_400
_RATE_LIMIT_WINDOW_SECONDS = 60
# Sprint 285 — see set_lead_state()'s own docstring.
_VALID_LEAD_STATES = {"pending", "contacted", "converted", "ignored"}
_DEFAULT_PLANS = {
    "free": {
        "name": "Free",
        "limits": {
            "users": 1,
            "requests_per_day": 100,
            "projects": 1,
            "requests_per_minute": 100,
            # domains/alerts_per_hour (Sprint 265): monetization limits for
            # the CDN/metrics subsystem (self-service domain registration,
            # alert-webhook rate limiting) — added here rather than in a
            # new, separate plan store, since this dict is already the
            # single source of truth `get_organization_plan()`/
            # `set_organization_plan()`/`get_plan_limits()` all read from.
            "domains": 1,
            "alerts_per_hour": 50,
        },
    },
    "pro": {
        "name": "Pro",
        "limits": {
            "users": 5,
            "requests_per_day": 1000,
            "projects": 10,
            "requests_per_minute": 1000,
            "domains": 5,
            "alerts_per_hour": 500,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "limits": {
            "users": -1,
            "requests_per_day": -1,
            "projects": -1,
            "requests_per_minute": -1,
            # -1 ("unlimited"), not a large finite number like the
            # spec's own 999/9999 — every other enterprise limit in this
            # dict already uses -1 as the "no limit" sentinel
            # (check_limit() explicitly short-circuits on it); a finite
            # number here would be the only limit type actually enforced
            # against Enterprise customers, inconsistent with the other
            # three.
            "domains": -1,
            "alerts_per_hour": -1,
        },
    },
}


class PlatformAuth:
    def __init__(
        self,
        secret: bytes | None = None,
        session_ttl: int = _DEFAULT_SESSION_TTL,
        storage: PlatformStorage | None = None,
        cache: PlatformCache | None = None,
        audit: PlatformAudit | None = None,
        metrics: PlatformMetrics | None = None,
        logger: PlatformLogger | None = None,
        repository: AuthRepository | None = None,
    ):
        """Fase 1 (auth persistence). `repository` is additive and
        optional: when `None` (the default — every one of the ~430
        existing call sites and ~400 existing tests never pass it), every
        method below runs exactly the same in-memory dict logic as
        before, untouched. When a repository IS provided (only the
        production composition root does this — see
        `app/api/dependencies/auth.py`), the same methods delegate to real
        Postgres instead, through the small `self._get_user()`/
        `self._get_org()` read helpers and explicit `if self._repository
        is not None:` branches at each write site. `self._users`/
        `self._organizations`/`self._sessions`/`self._usage` keep existing
        even in repository mode (harmless — nothing ever reads or writes
        them in that mode) rather than making them conditionally absent,
        since several call sites (and dict-mode-only tests) already assume
        they exist as attributes.
        """
        self._storage = storage or InMemoryStorage()
        self._cache = cache
        self._audit = audit
        self._metrics = metrics
        self._logger = logger
        self._rate_limiter = PlatformRateLimiter()
        self._repository = repository

        data = self._storage.load()

        self._users: dict[str, dict] = data.get("users", {})
        self._sessions: dict[str, dict] = {}
        self._organizations: dict[str, dict] = data.get("organizations", {})
        self._plans: dict[str, dict] = {
            plan_id: {"name": plan["name"], "limits": dict(plan["limits"])}
            for plan_id, plan in _DEFAULT_PLANS.items()
        }
        self._usage: dict[str, dict] = data.get("usage", {})

        self._secret = secret or os.urandom(32)
        self._ttl = session_ttl

    def _persist(self) -> None:
        if self._repository is not None:
            # Repository-mode writes already commit to Postgres at the
            # point they happen (see e.g. AuthRepository.update_organization);
            # there's no in-memory blob left to flush here.
            return

        self._storage.save(
            {
                "users": self._users,
                "organizations": self._organizations,
                "usage": self._usage,
            }
        )

    def _get_user(self, email: str) -> dict | None:
        """Read helper used by every user-lookup method below. In
        dict-mode this returns the *live* `self._users[email]` reference
        (existing mutation-in-place callers keep working); in
        repository-mode it returns a fresh dict built from the Postgres
        row — mutating write paths never rely on mutating this returned
        value, they always go through an explicit repository call."""
        if self._repository is not None:
            return self._repository.get_user(email)

        return self._users.get(email)

    def _get_org(self, org_id: str) -> dict | None:
        """Same contract as `_get_user()`, for organizations."""
        if self._repository is not None:
            return self._repository.get_organization(org_id)

        return self._organizations.get(org_id)

    def _invalidate_user_cache(self, email: str) -> None:
        if self._cache is None:
            return

        self._cache.delete(f"user_role:{email}")
        self._cache.delete(f"user_permissions:{email}")
        self._cache.delete(f"user_org:{email}")

    def _invalidate_org_cache(self, org_id: str) -> None:
        if self._cache is None:
            return

        self._cache.delete(f"org_plan:{org_id}")

    def _log_event(
        self,
        event: str,
        email: str | None,
        organization_id: str | None,
        metadata: dict | None = None,
    ) -> None:
        if self._audit is None:
            return

        self._audit.log_event(event, email, organization_id, metadata)

    def _increment(
        self, name: str, value: int = 1, organization_id: str | None = None
    ) -> None:
        if self._metrics is None:
            return

        self._metrics.increment(name, value, organization_id=organization_id)

    def _timing(
        self, name: str, duration: float, organization_id: str | None = None
    ) -> None:
        if self._metrics is None:
            return

        self._metrics.timing(name, duration, organization_id=organization_id)

    def _log(
        self,
        level: str,
        message: str,
        correlation_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        if self._logger is None:
            return

        self._logger.log(level, message, correlation_id=correlation_id, metadata=metadata)

    def register_user(
        self,
        email: str,
        password: str,
        role: str = "user",
        permissions: list[str] | None = None,
        organization_id: str | None = None,
        organization_role: str = "member",
        correlation_id: str | None = None,
    ) -> None:
        salt = os.urandom(16)
        password_hash = self._hash(password, salt)

        if organization_id is None:
            organization_id = self.create_organization(f"{email}'s organization")
            organization_role = "owner"

        if self._repository is not None:
            self._repository.create_or_replace_user(
                email,
                salt,
                password_hash,
                role,
                permissions or [],
                organization_id,
                organization_role,
            )
        else:
            self._users[email] = {
                "salt": salt,
                "hash": password_hash,
                "role": role,
                "permissions": permissions or [],
                "organization_id": organization_id,
                "organization_role": organization_role,
            }

        self.add_user_to_organization(email, organization_id)
        self._invalidate_user_cache(email)
        self._persist()
        self._log_event("user_registered", email, organization_id, {"role": role})
        self._increment("auth.register", organization_id=organization_id)
        self._log(
            "INFO",
            "auth.register",
            correlation_id=correlation_id,
            metadata={"email": email, "organization_id": organization_id, "role": role},
        )

    def create_organization(self, name: str) -> str:
        org_id = uuid.uuid4().hex

        if self._repository is not None:
            self._repository.create_organization(org_id, name)
        else:
            self._organizations[org_id] = {
                "name": name,
                "created_at": int(time.time()),
                "users": [],
                "plan": "free",
            }

        self._persist()
        self._log_event("organization_created", None, org_id, {"name": name})
        self._increment("org.created", organization_id=org_id)

        return org_id

    def get_user_organization(self, email: str) -> str | None:
        cache_key = f"user_org:{email}"

        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        user = self._get_user(email)

        if user is None:
            return None

        organization_id = user["organization_id"]

        if self._cache is not None:
            self._cache.set(cache_key, organization_id)

        return organization_id

    def get_user_organization_role(self, email: str) -> str | None:
        user = self._get_user(email)

        if user is None:
            return None

        return user["organization_role"]

    def has_any_admin(self) -> bool:
        """Used to gate self-registration with `role="admin"` (see
        `POST /auth/register`): `role` is a client-supplied field on that
        public, unauthenticated endpoint with no other restriction, so once
        any admin exists, self-registering as one must stop working —
        otherwise anyone on the internet could grant themselves admin at
        any time. The very first admin in a fresh deployment is still
        whoever registers first with `role="admin"` (this method returns
        `False` until then) — a narrower, harder-to-close bootstrap gap,
        consistent with this whole platform's registration already having
        no invite/approval gate for regular accounts either.
        """
        if self._repository is not None:
            return self._repository.has_any_admin()

        return any(user["role"] == "admin" for user in self._users.values())

    def get_organization(self, org_id: str) -> dict | None:
        return self._get_org(org_id)

    def list_organizations(self) -> dict[str, dict]:
        """Sprint 272. `BillingMetrics` needs to iterate every
        organization to aggregate MRR/ARR/churn — the spec's own version
        read `getattr(auth, "_organizations", {})` directly from the
        router/service layer, reaching past `PlatformAuth` into its
        private state exactly the way this codebase's established
        convention forbids (see e.g. `LoaderMetricsStore`'s delegation
        methods, `_require_own_tenant_id()` in tenants.py, ...). A plain
        `dict(...)` copy, not the live dict, so a caller iterating it
        can't accidentally mutate organization state through it.
        """
        if self._repository is not None:
            return self._repository.list_organizations()

        return dict(self._organizations)

    def get_organization_plan(self, org_id: str) -> str | None:
        cache_key = f"org_plan:{org_id}"

        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        org = self._get_org(org_id)

        if org is None:
            return None

        plan = org["plan"]

        if self._cache is not None:
            self._cache.set(cache_key, plan)

        return plan

    def set_organization_plan(self, org_id: str, plan: str) -> None:
        """Sprint 275 adds plan-history tracking ahead of the actual plan
        change, so `expansion_revenue()`/`contraction_revenue()` can
        reconstruct upgrade/downgrade deltas later. Validates `plan`,
        raises `LookupError` for a nonexistent org, invalidates the plan
        cache, and only appends a history entry when the plan actually
        changes — see `test_set_organization_plan_invalido_nao_registra_
        historico` (a rejected plan change must not create a phantom
        `plan_history` entry, and an org that never had a successful plan
        change must not have a `plan_history` key at all).
        """
        if plan not in self._plans:
            raise ValueError(f"Unknown plan '{plan}'")

        org = self._get_org(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        old_plan = org.get("plan", "free")
        new_history: list | None = None

        if old_plan != plan:
            new_history = list(org.get("plan_history", []))
            new_history.append({"from": old_plan, "to": plan, "timestamp": int(time.time())})

        if self._repository is not None:
            fields: dict = {"plan": plan}
            if new_history is not None:
                fields["plan_history"] = new_history
            self._repository.update_organization(org_id, **fields)
        else:
            if new_history is not None:
                org["plan_history"] = new_history
            org["plan"] = plan

        self._invalidate_org_cache(org_id)
        self._persist()

    def set_organization_plan_for_test(self, org_id: str, plan: str) -> None:
        """Test-support only: writes the plan directly, bypassing cache
        invalidation and plan-history tracking, so cache-staleness tests
        (e.g. `test_get_organization_plan_usa_cache_quando_disponivel`)
        can prove a cached value keeps being served after the underlying
        data changes out of band. Use `set_organization_plan()` for
        anything that isn't specifically testing that."""
        if self._repository is not None:
            self._repository.update_organization(org_id, plan=plan)
        elif org_id in self._organizations:
            self._organizations[org_id]["plan"] = plan

    def set_retention_flag(self, org_id: str, flag: bool) -> None:
        """Sprint 278. `BillingDecisionEngine.auto_retention()` needs a
        way to mark a high-churn-risk organization for follow-up.
        """
        org = self._get_org(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        if self._repository is not None:
            self._repository.update_organization(org_id, retention_flag=flag)
        else:
            org["retention_flag"] = flag

        self._persist()

    def get_retention_flag(self, org_id: str) -> bool:
        org = self._get_org(org_id)

        if org is None:
            return False

        return bool(org.get("retention_flag", False))

    def set_lead_state(self, org_id: str, lead_type: str, state: str) -> None:
        """Sprint 285. `LeadExecutionTracker` needs somewhere durable to
        record what a sales rep has done about a given playbook lead
        (Sprint 284's `SalesPlaybookEngine`) — storing per-`lead_type`
        state under `org["lead_states"]` rather than a single flat field,
        since one organization can independently be a lead for more than
        one `lead_type` at once.

        Only validates `state` here, not `lead_type` — `PlatformAuth`
        has no business knowing about `"upgrade_offer"`/`"retention_
        offer"`/`"expansion_offer"` as concepts; that vocabulary belongs
        to `LeadExecutionTracker` (app/platform/revenue/lead_execution.py),
        which validates it before ever calling this method.
        """
        if state not in _VALID_LEAD_STATES:
            raise ValueError(f"Unknown lead state '{state}'")

        org = self._get_org(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        if self._repository is not None:
            lead_states = dict(org.get("lead_states", {}))
            lead_states[lead_type] = state
            self._repository.update_organization(org_id, lead_states=lead_states)
        else:
            org.setdefault("lead_states", {})[lead_type] = state

        self._persist()

    def get_lead_state(self, org_id: str, lead_type: str) -> str:
        org = self._get_org(org_id)

        if org is None:
            return "pending"

        return org.get("lead_states", {}).get(lead_type, "pending")

    def rename_organization(self, org_id: str, name: str) -> None:
        """Sprint 265's tenant-onboarding "name your business" step
        (`POST /tenants`) — every organization already gets a default
        name at creation (`f"{email}'s organization"`, `register_user()`)
        but had no way to change it afterward.
        """
        org = self._get_org(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        if self._repository is not None:
            self._repository.update_organization(org_id, name=name)
        else:
            org["name"] = name

        self._persist()
        self._log_event("organization_renamed", None, org_id, {"name": name})

    def set_organization_created_at(self, org_id: str, timestamp: int) -> None:
        """Test-support only (Fase 1): backdates an organization's
        creation time. `BillingAnalytics`/`BillingDecisionEngine`'s
        tenure-based scoring needs an org "created N days ago" and there
        is no production path that ever needs to change this after the
        fact — this exists purely so those tests don't have to sleep in
        real time."""
        if self._repository is not None:
            self._repository.update_organization(
                org_id, created_at=datetime.fromtimestamp(timestamp, tz=timezone.utc)
            )
        elif org_id in self._organizations:
            self._organizations[org_id]["created_at"] = timestamp

    def get_plan_limits(self, plan: str) -> dict:
        plan_def = self._plans.get(plan)

        if plan_def is None:
            return {}

        return plan_def["limits"]

    def get_usage_limit(self, tenant_id: str, metric: str) -> int:
        """Sprint 270. Resolves the tenant's plan first, then looks up
        the limit on that plan — `get_plan_limits()` takes a *plan name*
        (`"free"`/`"pro"`/`"enterprise"`), not a tenant/organization id.
        """
        plan = self.get_organization_plan(tenant_id)
        limits = self.get_plan_limits(plan)

        return limits.get(metric, -1)

    def set_stripe_ids(
        self, org_id: str, customer_id: str | None, subscription_id: str | None
    ) -> None:
        """Sprint 269 — persists the Stripe customer/subscription linked
        to this organization. Either id may be omitted (`None`) without
        clearing the other — a `customer.subscription.updated` event, for
        instance, has no reason to touch `stripe_customer_id` at all.
        """
        org = self._get_org(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        fields: dict = {}

        if customer_id is not None:
            fields["stripe_customer_id"] = customer_id

        if subscription_id is not None:
            fields["stripe_subscription_id"] = subscription_id

        if fields:
            if self._repository is not None:
                self._repository.update_organization(org_id, **fields)
            else:
                org.update(fields)

        self._persist()

    def get_stripe_ids(self, org_id: str) -> dict:
        org = self._get_org(org_id)

        if org is None:
            return {}

        return {
            "stripe_customer_id": org.get("stripe_customer_id"),
            "stripe_subscription_id": org.get("stripe_subscription_id"),
        }

    def find_organization_by_stripe_customer(self, customer_id: str) -> str | None:
        """Reverse lookup (Sprint 269): most Stripe webhook events after
        checkout (`invoice.payment_failed`, `customer.subscription.
        updated`/`deleted`) carry a `customer` id but not necessarily the
        original checkout metadata (`org_id`/`plan`).
        """
        if self._repository is not None:
            return self._repository.find_organization_by_stripe_customer(customer_id)

        for org_id, org in self._organizations.items():
            if org.get("stripe_customer_id") == customer_id:
                return org_id

        return None

    def set_subscription_status(self, org_id: str, status: str) -> None:
        """Distinct from `plan` — a `past_due` subscription (a failed
        payment Stripe is still retrying) keeps its current plan/limits
        during that grace window; only `customer.subscription.deleted`
        also reverts the plan itself, via the webhook handler's own logic
        in `stripe_service.py`, not this method.
        """
        org = self._get_org(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        fields: dict = {"subscription_status": status}
        canceled_at_epoch: int | None = None

        # Sprint 273's BillingAnalytics.churn_over_time() needs to know
        # *when* a cancellation happened to bucket it by month — nothing
        # in this codebase persisted that before now. Stamped here, the
        # single choke point both Stripe cancellation paths
        # (`customer.subscription.deleted` and `customer.subscription.
        # updated` mapping to "canceled") already funnel through via
        # `stripe_webhook()` in billing.py, rather than in
        # `stripe_service.py` itself.
        if status == "canceled":
            canceled_at_epoch = int(time.time())
            fields["canceled_at"] = canceled_at_epoch

        if self._repository is not None:
            repo_fields = dict(fields)
            if canceled_at_epoch is not None:
                repo_fields["canceled_at"] = datetime.fromtimestamp(
                    canceled_at_epoch, tz=timezone.utc
                )
            self._repository.update_organization(org_id, **repo_fields)
        else:
            org.update(fields)

        self._persist()

    def get_subscription_status(self, org_id: str) -> str | None:
        org = self._get_org(org_id)

        if org is None:
            return None

        return org.get("subscription_status")

    def add_user_to_organization(self, email: str, org_id: str) -> None:
        if self._repository is not None:
            org = self._repository.get_organization(org_id)

            if org is None:
                return

            added = self._repository.add_membership(email, org_id)

            if added:
                self._invalidate_user_cache(email)
                self._log_event("user_added_to_org", email, org_id, {})
        else:
            org = self._organizations.get(org_id)

            if org is None:
                return

            if email not in org["users"]:
                org["users"].append(email)
                self._invalidate_user_cache(email)
                self._persist()
                self._log_event("user_added_to_org", email, org_id, {})

    def _usage_record(self, org_id: str) -> dict:
        """Dict-mode only. Repository-mode usage reads/writes go through
        `get_usage_for_org()`/`increment_usage()` directly — there's no
        single "live record" object once usage is a per-day Postgres row
        (see `AuthRepository.get_usage()`/`increment_usage()`)."""
        today = int(time.time()) // _SECONDS_PER_DAY
        usage = self._usage.get(org_id)

        if usage is None or usage["last_reset"] != today:
            usage = {"requests_today": 0, "last_reset": today}
            self._usage[org_id] = usage

        return usage

    def get_usage_for_org(self, org_id: str) -> int:
        """Today's request count for this organization. Public (unlike
        the dict-mode-only `_usage_record()`) so both production callers
        and tests have one stable way to read it regardless of storage
        mode."""
        if self._repository is not None:
            return self._repository.get_usage(org_id, datetime.now(timezone.utc).date())

        return self._usage_record(org_id)["requests_today"]

    def expire_usage_for_org(self, org_id: str) -> None:
        """Test-support only (Fase 1): clears today's usage bucket for
        this org, so the next read/increment starts over at 0 —
        simulates a day boundary without waiting for one. Dict-mode drops
        the cached bucket entirely (equivalent to backdating
        `last_reset`); repo-mode deletes today's row (a real day rollover
        needs no such call — a new calendar date is already a new primary
        key and starts at 0 on its own)."""
        if self._repository is not None:
            self._repository.clear_usage(org_id, datetime.now(timezone.utc).date())
        else:
            self._usage.pop(org_id, None)

    def _current_usage(self, org_id: str, limit_key: str) -> int | None:
        if limit_key == "requests_per_day":
            return self.get_usage_for_org(org_id)

        if limit_key == "users":
            org = self._get_org(org_id)
            return len(org["users"]) if org is not None else 0

        return None

    def check_limit(self, org_id: str, limit_key: str) -> None:
        plan = self.get_organization_plan(org_id)
        limit_value = self.get_plan_limits(plan).get(limit_key)

        if limit_value is None or limit_value == -1:
            return

        current_value = self._current_usage(org_id, limit_key)

        if current_value is None:
            return

        if current_value >= limit_value:
            raise PermissionError("Limit exceeded")

    def increment_usage(self, org_id: str, limit_key: str) -> None:
        if limit_key != "requests_per_day":
            return

        if self._repository is not None:
            self._repository.increment_usage(org_id, datetime.now(timezone.utc).date())
        else:
            usage = self._usage_record(org_id)
            usage["requests_today"] += 1

        self._persist()

    def check_rate_limit(self, email: str, correlation_id: str | None = None) -> None:
        org_id = self.get_user_organization(email)
        plan = self.get_organization_plan(org_id)
        limit = self.get_plan_limits(plan).get("requests_per_minute")

        if not self._rate_limiter.allow(f"user:{email}", limit, _RATE_LIMIT_WINDOW_SECONDS):
            self._log_event("rate_limit_exceeded", email, org_id, {"scope": "user"})
            self._increment("rate_limit.hit", organization_id=org_id)
            self._log(
                "WARN",
                "auth.rate_limited",
                correlation_id=correlation_id,
                metadata={"email": email, "organization_id": org_id, "scope": "user"},
            )
            raise RateLimitExceeded("Rate limit exceeded")

        if org_id is not None:
            allowed = self._rate_limiter.allow(f"org:{org_id}", limit, _RATE_LIMIT_WINDOW_SECONDS)
            if not allowed:
                self._log_event("rate_limit_exceeded", email, org_id, {"scope": "org"})
                self._increment("rate_limit.hit", organization_id=org_id)
                self._log(
                    "WARN",
                    "auth.rate_limited",
                    correlation_id=correlation_id,
                    metadata={"email": email, "organization_id": org_id, "scope": "org"},
                )
                raise RateLimitExceeded("Rate limit exceeded")

    def get_user_role(self, email: str) -> str | None:
        cache_key = f"user_role:{email}"

        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        user = self._get_user(email)

        if user is None:
            return None

        role = user["role"]

        if self._cache is not None:
            self._cache.set(cache_key, role)

        return role

    def set_user_role_for_test(self, email: str, role: str) -> None:
        """Test-support only: changes a user's role WITHOUT invalidating
        the role cache — used by cache-staleness tests (e.g.
        `test_get_user_role_usa_cache_quando_disponivel`) that need to
        prove a cached value keeps being served after the underlying data
        changes out of band. There is no production path that would ever
        want this; role changes normally go through `register_user()`."""
        if self._repository is not None:
            self._repository.set_user_fields(email, role=role)
        elif email in self._users:
            self._users[email]["role"] = role

    def get_user_permissions(self, email: str) -> list[str]:
        cache_key = f"user_permissions:{email}"

        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        user = self._get_user(email)

        if user is None:
            return []

        permissions = user["permissions"]

        if self._cache is not None:
            self._cache.set(cache_key, permissions)

        return permissions

    def set_user_permissions_for_test(self, email: str, permissions: list[str]) -> None:
        """Test-support only — same rationale as `set_user_role_for_test()`."""
        if self._repository is not None:
            self._repository.set_user_fields(email, permissions=list(permissions))
        elif email in self._users:
            self._users[email]["permissions"] = permissions

    def set_user_organization_for_test(self, email: str, organization_id: str | None) -> None:
        """Test-support only — same rationale as `set_user_role_for_test()`,
        also used to simulate an orphaned user (`organization_id=None`)
        without going through any real organization-removal flow."""
        if self._repository is not None:
            self._repository.set_user_fields(email, organization_id=organization_id)
        elif email in self._users:
            self._users[email]["organization_id"] = organization_id

    def get_user_credentials_for_test(self, email: str) -> dict:
        """Test-support only: exposes the stored password salt/hash so
        tests can assert they're non-trivial, per-user-unique bytes
        without either handling a real password in plaintext or reaching
        into `_users` directly."""
        user = self._get_user(email)
        return {"salt": user["salt"], "hash": user["hash"]}

    def _hash(self, password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)

    def _sign(self, payload: str) -> str:
        sig = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{sig}"

    def _verify(self, token: str) -> str | None:
        try:
            payload, sig = token.rsplit(".", 1)
        except ValueError:
            return None

        expected = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(sig, expected):
            return None

        return payload

    def login(
        self, email: str, password: str, correlation_id: str | None = None
    ) -> dict | None:
        login_started_at = time.perf_counter()

        try:
            user = self._get_user(email)

            if user is None:
                self._log(
                    "WARN",
                    "auth.login.failed",
                    correlation_id=correlation_id,
                    metadata={"email": email},
                )
                return None

            candidate_hash = self._hash(password, user["salt"])

            if not hmac.compare_digest(candidate_hash, user["hash"]):
                self._log(
                    "WARN",
                    "auth.login.failed",
                    correlation_id=correlation_id,
                    metadata={"email": email, "organization_id": user["organization_id"]},
                )
                return None

            issued_at = int(time.time())
            session_id = uuid.uuid4().hex
            token = self._sign(f"{session_id}:{issued_at}")

            if self._repository is not None:
                self._repository.create_session(
                    token,
                    email,
                    user["organization_id"],
                    user["role"],
                    user["permissions"],
                    issued_at,
                    self._ttl,
                )
            else:
                self._sessions[token] = {
                    "email": email,
                    "issued_at": issued_at,
                    "organization_id": user["organization_id"],
                    "role": user["role"],
                    "permissions": user["permissions"],
                }

            self._log_event("user_logged_in", email, user["organization_id"], {})
            self._increment("auth.login.success", organization_id=user["organization_id"])
            self._log(
                "INFO",
                "auth.login.success",
                correlation_id=correlation_id,
                metadata={"email": email, "organization_id": user["organization_id"]},
            )

            return {
                "token": token,
                "email": email,
            }
        finally:
            org_id_for_timing = user["organization_id"] if user is not None else None
            self._timing(
                "auth.login.duration",
                time.perf_counter() - login_started_at,
                organization_id=org_id_for_timing,
            )

    def get_session(self, token: str) -> dict | None:
        payload = self._verify(token)

        if payload is None:
            return None

        if self._repository is not None:
            session = self._repository.get_session(token)

            if session is None:
                return None

            if int(time.time()) - session["issued_at"] > self._ttl:
                self._repository.delete_session(token)
                return None

            return session

        session = self._sessions.get(token)

        if session is None:
            return None

        if int(time.time()) - session["issued_at"] > self._ttl:
            del self._sessions[token]
            return None

        return session

    def is_authenticated(self, token: str) -> bool:
        return self.get_session(token) is not None

    def logout(self, token: str) -> None:
        if self._repository is not None:
            session = self._repository.delete_session(token)
        else:
            session = self._sessions.pop(token, None)

        if session is not None:
            self._log_event("user_logged_out", session["email"], session["organization_id"], {})

    def exists(self, email: str) -> bool:
        if self._repository is not None:
            return self._repository.user_exists(email)

        return email in self._users
