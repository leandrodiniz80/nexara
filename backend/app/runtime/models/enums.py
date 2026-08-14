import enum


class ExecutionType(str, enum.Enum):
    """Closed vocabulary for what kind of thing an Execution ran. Only WORKFLOW and
    AUTOMATION have a real Executor registered by build_default_runtime_engine()
    today; PIPELINE/AGENT/CUSTOM exist so the ExecutionType vocabulary — and
    therefore RuntimeEngine's public API — never needs to change shape when a
    future sprint adds an Executor for one of them."""

    WORKFLOW = "workflow"
    AUTOMATION = "automation"
    JOB = "job"
    PIPELINE = "pipeline"
    AGENT = "agent"
    CUSTOM = "custom"


class ExecutionStatus(str, enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
