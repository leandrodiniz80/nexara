class SalesPlaybookEngine:
    """Turns `RevenueActivationEngine`'s scored leads into ready-to-send
    message payloads (Sprint 284) — a message, an action tag, and a
    priority, nothing more. This class never sends anything: no
    WhatsApp/email/CRM integration exists in this codebase, and this
    sprint's own explicit rules say not to build one yet
    ("não enviar mensagem de verdade", "não integrar com WhatsApp
    ainda"). Every method here is pure read-and-transform over
    `self.activation`'s own already-computed, already-scored lead
    lists — nothing here recalculates a score, a usage ratio, or a
    churn risk by hand.

    `lead_state_tracker` (optional, Sprint 285, `None` by default — same
    "feature toggle, no crash" shape as `stripe_sync`/`notifier` on
    `BillingDecisionEngine`) attaches each entry's current `"state"`
    (`"pending"`/`"contacted"`/`"converted"`/`"ignored"` — see
    `LeadExecutionTracker`, app/platform/revenue/lead_execution.py) so a
    consumer of the playbook can tell which leads a rep already acted
    on. `None` means every entry reports `"pending"`, which is exactly
    what Sprint 284's own tests already expect (none of them pass a
    tracker), so that sprint's existing behavior is unchanged by
    default.
    """

    def __init__(self, activation_engine, lead_state_tracker=None):
        self.activation = activation_engine
        self.lead_state_tracker = lead_state_tracker

    def _lead_state(self, org_id: str, lead_type: str) -> str:
        if self.lead_state_tracker is None:
            return "pending"

        return self.lead_state_tracker.get_state(org_id, lead_type)

    def generate_playbook(self) -> dict:
        return {
            "high_intent": self._high_intent_playbook(),
            "churn_risk": self._churn_playbook(),
            "expansion": self._expansion_playbook(),
        }

    def _high_intent_playbook(self) -> list[dict]:
        """Message personalization (Sprint 284's own Part 5) uses each
        lead's own `usage_ratio` — already present on `high_intent_
        leads()`'s own returned dicts (Sprint 283) — rather than calling
        `self.activation.analytics.usage_ratio()` again: that would be
        both a redundant recomputation of a value already sitting right
        there, and a two-level reach-through (`activation.analytics`)
        this class doesn't otherwise need at all.
        """
        leads = self.activation.high_intent_leads()

        playbook = [
            {
                "org_id": lead["org_id"],
                "message": (
                    f"Seu uso atual está em {lead['usage_ratio'] * 100:.0f}% do "
                    "plano. Quer liberar mais capacidade?"
                ),
                "action": "upgrade_offer",
                "priority": lead["score"],
                "state": self._lead_state(lead["org_id"], "upgrade_offer"),
            }
            for lead in leads
        ]

        return sorted(playbook, key=lambda entry: entry["priority"], reverse=True)

    def _churn_playbook(self) -> list[dict]:
        """The spec's own version of this method built a one-item list
        literal referencing an undefined loop variable `l` — no `for l
        in leads` clause at all, so calling it would raise `NameError`
        immediately, and even if it hadn't, it would only ever return
        one entry regardless of how many churn-risk leads actually
        existed. Fixed to a proper comprehension over every lead.
        """
        leads = self.activation.churn_risk_leads()

        playbook = [
            {
                "org_id": lead["org_id"],
                "message": "Percebemos uma queda no uso. Podemos te ajudar a "
                "extrair mais valor?",
                "action": "retention_offer",
                "priority": lead["score"],
                "state": self._lead_state(lead["org_id"], "retention_offer"),
            }
            for lead in leads
        ]

        return sorted(playbook, key=lambda entry: entry["priority"], reverse=True)

    def _expansion_playbook(self) -> list[dict]:
        """Same undefined-loop-variable bug as `_churn_playbook()`
        (the spec's own version), fixed the same way.
        """
        leads = self.activation.expansion_opportunities()

        playbook = [
            {
                "org_id": lead["org_id"],
                "message": "Seu uso está crescendo — faz sentido evoluir seu plano.",
                "action": "expansion_offer",
                "priority": lead["score"],
                "state": self._lead_state(lead["org_id"], "expansion_offer"),
            }
            for lead in leads
        ]

        return sorted(playbook, key=lambda entry: entry["priority"], reverse=True)
