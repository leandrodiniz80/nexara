import enum


class OrchestrationStage(str, enum.Enum):
    """Which step of the coordination pipeline an orchestration reached —
    Decision -> Rules -> Runtime -> Observability -> Completed. Used to report
    exactly where a failed orchestration stopped, without the Orchestrator
    needing to know anything about *why* a given port failed.
    """

    DECISION = "decision"
    RULES = "rules"
    RUNTIME = "runtime"
    OBSERVABILITY = "observability"
    COMPLETED = "completed"
