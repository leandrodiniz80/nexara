import enum


class MissionStatus(str, enum.Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class MissionPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
