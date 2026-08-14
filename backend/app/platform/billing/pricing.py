"""Centralized plan pricing (Sprint 272).

Hardcoded, not read from Stripe at request time — this dashboard is
explicitly meant to work off locally persisted state only (no Stripe
runtime dependency, per this sprint's own decision), and Stripe's own
Price objects don't expose a stable "current amount" lookup by plan name
that this codebase already resolves anywhere. If these amounts ever need
to change, they should stay in sync with STRIPE_PRICE_ID_PRO/
STRIPE_PRICE_ID_ENTERPRISE in app/core/config.py by hand.
"""

PLAN_PRICING = {
    "free": 0,
    "pro": 99,
    "enterprise": 299,
}


def get_plan_price(plan: str) -> int:
    return PLAN_PRICING.get(plan, 0)
