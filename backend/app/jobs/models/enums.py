import enum


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
