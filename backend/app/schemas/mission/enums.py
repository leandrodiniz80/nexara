import enum


class PipelineHealth(str, enum.Enum):
    """Computed by MissionEngine.summary() — a view-layer concept, never persisted, so
    it lives in schemas/ rather than models/ (unlike MissionStatus/MissionPriority)."""

    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
