import time
from datetime import datetime, timezone
from typing import Any, NamedTuple

from app.application.bus.bus_execution import BusExecution


class BusExecutionStart(NamedTuple):
    """The opaque handle `start()` returns and `finish()` consumes — carries
    exactly what's needed to measure and record one in-flight dispatch.
    """

    name: str
    started_at: datetime
    perf_start: float


class BusExecutionService:
    """Shared timing/recording infrastructure for CommandBus and QueryBus —
    knows nothing about commands or queries specifically, only how to time
    one named dispatch from start to finish and record the result as a
    BusExecution.
    """

    def start(self, name: str) -> BusExecutionStart:
        return BusExecutionStart(
            name=name,
            started_at=datetime.now(timezone.utc),
            perf_start=time.perf_counter(),
        )

    def finish(
        self,
        start: BusExecutionStart,
        *,
        success: bool,
        payload: Any | None = None,
        reason: str | None = None,
    ) -> BusExecution:
        return BusExecution(
            name=start.name,
            started_at=start.started_at,
            finished_at=datetime.now(timezone.utc),
            duration=time.perf_counter() - start.perf_start,
            success=success,
            payload=payload,
            reason=reason,
        )
