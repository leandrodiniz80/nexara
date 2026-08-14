_VALID_LEAD_TYPES = {"upgrade_offer", "retention_offer", "expansion_offer"}
_ACTION_TO_STATE = {"execute": "contacted", "ignore": "ignored", "convert": "converted"}


class LeadExecutionTracker:
    """Execution layer for `SalesPlaybookEngine`'s leads (Sprint 285) —
    the first thing in the whole revenue/billing-intelligence stack that
    actually persists state as a result of a sales action, rather than
    recomputing everything fresh on every call. Still no real message
    ever gets sent (no external integration exists in this codebase) —
    this only ever records *that* a rep took an action, via
    `PlatformAuth.set_lead_state()`, never anything about `plan`/
    `subscription_status`/Stripe.

    `lead_type` here is exactly the same vocabulary as `SalesPlaybookEngine`'s
    own playbook entries' `"action"` field (`"upgrade_offer"`/
    `"retention_offer"`/`"expansion_offer"`) — one organization can be
    at a different stage for each independently (e.g. already
    `"contacted"` for an upgrade offer while still `"pending"` for a
    retention offer), which is why state is tracked per (org_id,
    lead_type) pair, not one flat status per organization.
    """

    def __init__(self, auth):
        self.auth = auth

    def record_action(self, org_id: str, lead_type: str, action: str) -> dict:
        """Translates a sales-facing verb (`"execute"`/`"ignore"`/
        `"convert"`) into the stored noun-state (`"contacted"`/
        `"ignored"`/`"converted"`) — the endpoint layer speaks in verbs
        ("mark this lead executed"), `PlatformAuth.set_lead_state()`
        stores nouns (the current state a lead is *in*); this is the
        one place that translates between the two.

        Deliberately does *not* require `(org_id, lead_type)` to
        currently appear in a freshly-generated playbook — a rep marking
        something `"contacted"` today, whose org later stops qualifying
        as a live lead (its score/usage changed), shouldn't lose that
        history; the check here is only that the organization itself
        still exists, not that it's still a *current* candidate.

        Raises `ValueError` for an unrecognized `lead_type`/`action`,
        `LookupError` for a nonexistent organization — the caller (the
        router) maps both to the appropriate HTTP status.
        """
        if lead_type not in _VALID_LEAD_TYPES:
            raise ValueError(f"Unknown lead_type '{lead_type}'")

        if action not in _ACTION_TO_STATE:
            raise ValueError(f"Unknown action '{action}'")

        if self.auth.get_organization(org_id) is None:
            raise LookupError(f"Organization '{org_id}' not found")

        previous_state = self.auth.get_lead_state(org_id, lead_type)
        new_state = _ACTION_TO_STATE[action]

        self.auth.set_lead_state(org_id, lead_type, new_state)

        return {
            "org_id": org_id,
            "lead_type": lead_type,
            "previous_state": previous_state,
            "new_state": new_state,
        }

    def get_state(self, org_id: str, lead_type: str) -> str:
        return self.auth.get_lead_state(org_id, lead_type)

    def conversion_summary(self) -> dict:
        """Basic conversion tracking + the raw material for a future
        feedback loop (Sprint 285): per `lead_type`, how many
        organizations are in each state right now, plus a
        `conversion_rate`.

        `conversion_rate` is `converted / (contacted + converted +
        ignored)` — organizations still at the default `"pending"`
        (i.e. never actually acted on at all) are excluded from the
        denominator. Counting them would dilute this figure by every
        organization on the platform that was never even engaged with,
        which isn't what "conversion rate" is supposed to measure; a
        lead that was never contacted hasn't failed to convert, it just
        hasn't been tried yet.

        This method doesn't *do* anything with the numbers it returns —
        no auto-tuning of `score_lead()`'s weights, no automatic
        reprioritization. That's a genuinely different, much larger
        feature (a real feedback loop acting on this data) that wasn't
        asked for here; what this sprint provides is the data such a
        loop would need, not the loop itself.
        """
        summary = {}

        for lead_type in _VALID_LEAD_TYPES:
            counts = {"pending": 0, "contacted": 0, "converted": 0, "ignored": 0}

            for org in self.auth.list_organizations().values():
                state = org.get("lead_states", {}).get(lead_type, "pending")
                counts[state] += 1

            engaged = counts["contacted"] + counts["converted"] + counts["ignored"]
            conversion_rate = round(counts["converted"] / engaged, 4) if engaged else 0.0

            summary[lead_type] = {**counts, "conversion_rate": conversion_rate}

        return summary
