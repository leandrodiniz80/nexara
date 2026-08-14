from app.observability.engine.observability_engine import ObservabilityEngine


class ObservabilityAdapter:
    """Optional final step VerticalSlice calls to record what happened —
    registers a performance metric in the real ObservabilityEngine. Never
    called if the caller passes no ObservabilityAdapter to VerticalSlice.
    """

    def __init__(self, observability_engine: ObservabilityEngine) -> None:
        self.observability_engine = observability_engine

    def record(self, *, operation: str, execution_time: float, success: bool) -> None:
        self.observability_engine.register_metric(
            component="vertical_slice",
            operation=operation,
            execution_time=execution_time,
            success=success,
        )
