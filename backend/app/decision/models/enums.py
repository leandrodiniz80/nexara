import enum


class DecisionType(str, enum.Enum):
    """What kind of decision is being asked for — which registered Strategy
    handles it. Purely a label: the engine attaches no meaning to any of these
    beyond "which Strategy supports it"."""

    NEXT_ACTION = "next_action"
    WORKFLOW = "workflow"
    AUTOMATION = "automation"
    CHANNEL = "channel"
    PRIORITY = "priority"
    SCORE = "score"
    ROUTING = "routing"
    CUSTOM = "custom"
