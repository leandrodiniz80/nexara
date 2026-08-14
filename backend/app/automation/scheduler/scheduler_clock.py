from datetime import datetime, timezone


class SchedulerClock:
    """The one obvious place to get "the current time" from — Scheduler.tick(now)
    always takes an explicit `now` rather than calling this itself, so every tick
    stays deterministic and testable; this class exists only for whatever caller
    isn't testing with a fixed instant."""

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)
