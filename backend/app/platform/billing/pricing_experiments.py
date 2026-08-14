import hashlib

_VARIANTS = ("control", "price_up", "price_down")
_VARIANT_MULTIPLIERS = {"control": 1.0, "price_up": 1.2, "price_down": 0.8}


class PricingExperimentEngine:
    """Pricing A/B-test simulation layer (Sprint 282) — pure
    computation, no persistence of its own, and never wired into any
    real billing path: `get_plan_price()` (Sprint 272) stays the single
    source of truth for what a plan actually costs, `StripeService`/
    `StripeSyncService` never call anything here, and no real
    organization is ever actually charged a variant-adjusted price.
    `get_price_for_org()` answers "what *would* this org pay under this
    variant", strictly hypothetical, for `BillingAnalytics.
    pricing_experiment_metrics()` to simulate against.

    `analytics` (Sprint 282's own spec) isn't read by either method
    below — kept as a constructor parameter anyway, since a future
    sprint's more advanced recommendation logic (elasticity modeling,
    per the roadmap this sprint was previewed alongside) may need it,
    and removing it now would just mean re-adding it later.
    """

    def __init__(self, auth, analytics=None):
        self._auth = auth
        self._analytics = analytics

    def assign_variant(self, org_id: str) -> str:
        """Deterministic 3-way split via SHA-256 of `org_id`, not
        Python's built-in `hash()` — the built-in is deliberately
        randomized per-process (`PYTHONHASHSEED`) since Python 3.3, so
        the same organization could land in a *different* experiment
        group after every server restart, silently corrupting whatever
        experiment this assignment is meant to measure. SHA-256 gives
        the same digest for the same `org_id` forever, on any machine,
        in any process.
        """
        digest = hashlib.sha256(org_id.encode()).hexdigest()
        bucket = int(digest, 16) % len(_VARIANTS)

        return _VARIANTS[bucket]

    def get_price_for_org(self, org_id: str, base_price: float) -> float:
        variant = self.assign_variant(org_id)

        return round(base_price * _VARIANT_MULTIPLIERS[variant], 2)
