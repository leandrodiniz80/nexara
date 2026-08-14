class NotificationService:
    """Initial stub (Sprint 281) — `send()` doesn't actually deliver
    anything anywhere yet (no email/WhatsApp/CRM integration exists in
    this codebase); it exists so `BillingDecisionEngine` has somewhere
    to signal "an owner should probably hear about this" without
    coupling to a real channel yet. A future sprint (per the roadmap
    this one was scoped alongside) can replace the body without
    changing this method's shape.
    """

    def send(self, org_id: str, notification_type: str, payload: dict) -> dict:
        """`notification_type`, not `type` (the spec's own parameter
        name) — shadowing the `type` builtin, the same thing this
        codebase's own established convention already avoids elsewhere
        (e.g. `incident_type`, not `type`, as a query param name in
        cdn.py, Sprint 264).
        """
        return {"sent": True, "type": notification_type, "org_id": org_id}
