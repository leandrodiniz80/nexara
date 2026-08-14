from app.automation.exceptions.automation_exceptions import AutomationNotFoundError
from app.automation.models.automation import Automation


class AutomationRegistry:
    """Catalog of Automation *definitions*, keyed by name — register, look up,
    list, enable/disable. Unlike WorkflowRegistry there is no version history here:
    an Automation is mutated in place (enabled/disabled), never superseded by a new
    version.
    """

    def __init__(self) -> None:
        self._automations: dict[str, Automation] = {}

    def register(self, automation: Automation) -> Automation:
        self._automations[automation.name] = automation
        return automation

    def get(self, name: str) -> Automation:
        automation = self._automations.get(name)
        if automation is None:
            raise AutomationNotFoundError(name)
        return automation

    def list(self) -> list[Automation]:
        return list(self._automations.values())

    def enable(self, name: str) -> Automation:
        automation = self.get(name)
        automation.enabled = True
        return automation

    def disable(self, name: str) -> Automation:
        automation = self.get(name)
        automation.enabled = False
        return automation
