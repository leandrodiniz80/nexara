import hashlib
import hmac
import os
import time
import uuid

from app.platform.audit.platform_audit import PlatformAudit
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
    ):
        self._storage = storage or InMemoryStorage()
        self._cache = cache
        self._audit = audit
        self._metrics = metrics
        self._logger = logger
        self._rate_limiter = PlatformRateLimiter()

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
        self._storage.save(
            {
                "users": self._users,
                "organizations": self._organizations,
                "usage": self._usage,
            }
        )

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

        if organization_id is None:
            organization_id = self.create_organization(f"{email}'s organization")
            organization_role = "owner"

        self._users[email] = {
            "salt": salt,
            "hash": self._hash(password, salt),
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

        user = self._users.get(email)

        if user is None:
            return None

        organization_id = user["organization_id"]

        if self._cache is not None:
            self._cache.set(cache_key, organization_id)

        return organization_id

    def get_user_organization_role(self, email: str) -> str | None:
        user = self._users.get(email)

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
        return any(user["role"] == "admin" for user in self._users.values())

    def get_organization(self, org_id: str) -> dict | None:
        return self._organizations.get(org_id)

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
        return dict(self._organizations)

    def get_organization_plan(self, org_id: str) -> str | None:
        cache_key = f"org_plan:{org_id}"

        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        org = self._organizations.get(org_id)

        if org is None:
            return None

        plan = org["plan"]

        if self._cache is not None:
            self._cache.set(cache_key, plan)

        return plan

    def _append_plan_history(self, org_id: str, old_plan: str, new_plan: str) -> None:
        """Sprint 275. `BillingAnalytics.expansion_revenue()`/
        `contraction_revenue()` need to know when an organization's plan
        changed, and to/from what — nothing in this codebase persisted
        that before now.
        """
        org = self._organizations.get(org_id)

        if org is None:
            return

        history = org.setdefault("plan_history", [])
        history.append({"from": old_plan, "to": new_plan, "timestamp": int(time.time())})

    def set_organization_plan(self, org_id: str, plan: str) -> None:
        """Sprint 275 adds plan-history tracking (`_append_plan_history()`)
        ahead of the actual plan change, so `expansion_revenue()`/
        `contraction_revenue()` can reconstruct upgrade/downgrade deltas
        later. The spec's own version of this method replaced the whole
        thing wholesale, silently dropping three things this method
        already did and that other code already depends on: the
        `plan not in self._plans` validation (`ValueError` for an unknown
        plan — see `test_upgrade_plano_invalido_...`-style tests),
        `LookupError` for a nonexistent org (the spec's replacement
        silently no-ops instead), and `_invalidate_org_cache()` (without
        it, `get_organization_plan()`'s own cache — see right above —
        would keep serving the *old* plan until the cache entry expired
        on its own, even though the org's stored plan already changed).
        All three preserved here; only the history append is new.
        """
        if plan not in self._plans:
            raise ValueError(f"Unknown plan '{plan}'")

        org = self._organizations.get(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        old_plan = org.get("plan", "free")

        if old_plan != plan:
            self._append_plan_history(org_id, old_plan, plan)

        org["plan"] = plan
        self._invalidate_org_cache(org_id)
        self._persist()

    def set_retention_flag(self, org_id: str, flag: bool) -> None:
        """Sprint 278. `BillingDecisionEngine.auto_retention()` needs a
        way to mark a high-churn-risk organization for follow-up. The
        spec's own version mutated `org["retention_flag"] = True`
        directly on whatever `get_organization()` handed back — but that
        method returns this class's own *live* internal dict, not a
        copy, so mutating it from outside `PlatformAuth` bypasses
        `_persist()` entirely (the flag would vanish on the next storage
        reload) and is exactly the "reach into private state from
        outside the class" pattern this codebase's convention forbids
        everywhere else (`list_organizations()`'s own docstring makes
        the same point). A proper method instead, mirroring
        `set_organization_plan()`'s own shape.
        """
        org = self._organizations.get(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        org["retention_flag"] = flag
        self._persist()

    def get_retention_flag(self, org_id: str) -> bool:
        org = self._organizations.get(org_id)

        if org is None:
            return False

        return bool(org.get("retention_flag", False))

    def set_lead_state(self, org_id: str, lead_type: str, state: str) -> None:
        """Sprint 285. `LeadExecutionTracker` needs somewhere durable to
        record what a sales rep has done about a given playbook lead
        (Sprint 284's `SalesPlaybookEngine`) — mirrors `set_retention_
        flag()`'s own shape exactly, storing per-`lead_type` state under
        `org["lead_states"]` rather than a single flat field, since one
        organization can independently be a lead for more than one
        `lead_type` at once (e.g. both `"upgrade_offer"` and
        `"retention_offer"`).

        Only validates `state` here, not `lead_type` — `PlatformAuth`
        has no business knowing about `"upgrade_offer"`/`"retention_
        offer"`/`"expansion_offer"` as concepts; that vocabulary belongs
        to `LeadExecutionTracker` (app/platform/revenue/lead_execution.py),
        which validates it before ever calling this method.
        """
        if state not in _VALID_LEAD_STATES:
            raise ValueError(f"Unknown lead state '{state}'")

        org = self._organizations.get(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        org.setdefault("lead_states", {})[lead_type] = state
        self._persist()

    def get_lead_state(self, org_id: str, lead_type: str) -> str:
        org = self._organizations.get(org_id)

        if org is None:
            return "pending"

        return org.get("lead_states", {}).get(lead_type, "pending")

    def rename_organization(self, org_id: str, name: str) -> None:
        """Sprint 265's tenant-onboarding "name your business" step
        (`POST /tenants`) — every organization already gets a default
        name at creation (`f"{email}'s organization"`, `register_user()`)
        but had no way to change it afterward. No cache entry to
        invalidate (`get_organization()` isn't cached, unlike
        `get_organization_plan()`), so this mirrors
        `set_organization_plan()` minus that step.
        """
        org = self._organizations.get(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        org["name"] = name
        self._persist()
        self._log_event("organization_renamed", None, org_id, {"name": name})

    def get_plan_limits(self, plan: str) -> dict:
        plan_def = self._plans.get(plan)

        if plan_def is None:
            return {}

        return plan_def["limits"]

    def get_usage_limit(self, tenant_id: str, metric: str) -> int:
        """Sprint 270. The spec's own version called
        `self.get_plan_limits(tenant_id)` directly — but `get_plan_limits()`
        takes a *plan name* (`"free"`/`"pro"`/`"enterprise"`), not a
        tenant/organization id. A tenant_id would never match any real
        plan key, so `get_plan_limits()` would always return `{}`, and
        this method would always return the `-1` ("unlimited") default —
        silently making every tenant appear unlimited regardless of their
        actual plan, defeating this entire sprint's purpose. Fixed by
        resolving the tenant's plan first, exactly as every other plan-
        limit lookup in this codebase already does (e.g.
        `check_limit()`, or `/metrics/alerts`' own `get_alert_limit()`
        closure in cdn.py).
        """
        plan = self.get_organization_plan(tenant_id)
        limits = self.get_plan_limits(plan)

        return limits.get(metric, -1)

    def set_stripe_ids(
        self, org_id: str, customer_id: str | None, subscription_id: str | None
    ) -> None:
        """Sprint 269 — persists the Stripe customer/subscription linked
        to this organization, alongside its `plan`/`name` on the same
        `_organizations` record (not a separate `BillingManager`/store:
        this *is* the organization's own billing identity, the same
        reasoning Sprint 265 already applied to plans themselves). Either
        id may be omitted (`None`) without clearing the other — a
        `customer.subscription.updated` event, for instance, has no
        reason to touch `stripe_customer_id` at all.
        """
        org = self._organizations.get(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        if customer_id is not None:
            org["stripe_customer_id"] = customer_id

        if subscription_id is not None:
            org["stripe_subscription_id"] = subscription_id

        self._persist()

    def get_stripe_ids(self, org_id: str) -> dict:
        org = self._organizations.get(org_id)

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
        original checkout metadata (`org_id`/`plan`) — Stripe doesn't
        guarantee that metadata propagates from a Checkout Session onto
        every later event for the resulting subscription. A linear scan,
        not a maintained index: nothing else in `PlatformAuth` needs a
        reverse organization lookup, and this only ever runs on the
        (rare, not-hot-path) webhook delivery path, not per-request.
        """
        for org_id, org in self._organizations.items():
            if org.get("stripe_customer_id") == customer_id:
                return org_id

        return None

    def set_subscription_status(self, org_id: str, status: str) -> None:
        """Distinct from `plan` — a `past_due` subscription (a failed
        payment Stripe is still retrying) keeps its current plan/limits
        during that grace window; only `customer.subscription.deleted`
        (the subscription is genuinely gone, not just temporarily unpaid)
        also reverts the plan itself, via the webhook handler's own logic
        in `stripe_service.py`, not this method.
        """
        org = self._organizations.get(org_id)

        if org is None:
            raise LookupError(f"Organization '{org_id}' not found")

        org["subscription_status"] = status

        # Sprint 273's BillingAnalytics.churn_over_time() needs to know
        # *when* a cancellation happened to bucket it by month — nothing
        # in this codebase persisted that before now. Stamped here, the
        # single choke point both Stripe cancellation paths
        # (`customer.subscription.deleted` and `customer.subscription.
        # updated` mapping to "canceled") already funnel through via
        # `stripe_webhook()` in billing.py, rather than in
        # `stripe_service.py` itself.
        if status == "canceled":
            org["canceled_at"] = int(time.time())

        self._persist()

    def get_subscription_status(self, org_id: str) -> str | None:
        org = self._organizations.get(org_id)

        if org is None:
            return None

        return org.get("subscription_status")

    def add_user_to_organization(self, email: str, org_id: str) -> None:
        org = self._organizations.get(org_id)

        if org is None:
            return

        if email not in org["users"]:
            org["users"].append(email)
            self._invalidate_user_cache(email)
            self._persist()
            self._log_event("user_added_to_org", email, org_id, {})

    def _usage_record(self, org_id: str) -> dict:
        today = int(time.time()) // _SECONDS_PER_DAY
        usage = self._usage.get(org_id)

        if usage is None or usage["last_reset"] != today:
            usage = {"requests_today": 0, "last_reset": today}
            self._usage[org_id] = usage

        return usage

    def _current_usage(self, org_id: str, limit_key: str) -> int | None:
        if limit_key == "requests_per_day":
            return self._usage_record(org_id)["requests_today"]

        if limit_key == "users":
            org = self._organizations.get(org_id)
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
        if limit_key == "requests_per_day":
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

        user = self._users.get(email)

        if user is None:
            return None

        role = user["role"]

        if self._cache is not None:
            self._cache.set(cache_key, role)

        return role

    def get_user_permissions(self, email: str) -> list[str]:
        cache_key = f"user_permissions:{email}"

        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        user = self._users.get(email)

        if user is None:
            return []

        permissions = user["permissions"]

        if self._cache is not None:
            self._cache.set(cache_key, permissions)

        return permissions

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
            user = self._users.get(email)

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
        session = self._sessions.pop(token, None)

        if session is not None:
            self._log_event("user_logged_out", session["email"], session["organization_id"], {})

    def exists(self, email: str) -> bool:
        return email in self._users
