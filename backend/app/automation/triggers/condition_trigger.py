from app.automation.models.automation import Automation


class ConditionTrigger:
    """Decides whether a CONDITION Automation should fire. This sprint builds no
    expression/condition-evaluation engine — the caller has already evaluated
    whatever business condition matters (elsewhere, using real domain data this
    module is forbidden from knowing about) and simply reports the boolean
    outcome. Never runs a Workflow itself.
    """

    @staticmethod
    def should_fire(automation: Automation, *, condition_met: bool) -> bool:
        return automation.enabled and condition_met
