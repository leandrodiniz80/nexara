from app.automation.models.automation import Automation


class ManualTrigger:
    """Decides whether a MANUAL Automation should fire — never runs a Workflow
    itself, only AutomationEngine does that, after asking this class first.
    """

    @staticmethod
    def should_fire(automation: Automation) -> bool:
        """A manual trigger fires whenever asked, as long as the Automation is
        enabled — the "trigger condition" IS the caller's own decision to invoke
        it."""
        return automation.enabled
