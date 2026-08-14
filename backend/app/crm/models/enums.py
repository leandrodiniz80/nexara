import enum


class OpportunityStatus(str, enum.Enum):
    """Where a CRMOpportunity stands. Also reused on CRMStage.outcome — a stage
    IS what determines an opportunity's status: moving to a stage whose outcome is
    WON/LOST is what closes the opportunity, there is no separate close action.
    """

    OPEN = "open"
    WON = "won"
    LOST = "lost"


class ActivityType(str, enum.Enum):
    NOTE = "note"
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    TASK = "task"
