from pydantic import BaseModel, ConfigDict

from app.platform.health.health_manager import HealthManager


class HealthExecutor(BaseModel):
    """The platform's official infrastructure for running HealthChecks — a
    frozen model holding exactly one collaborator. `run()` walks
    `manager.checks()` in order, calls `check()` on each, and returns the
    boolean results as a tuple in the same order. No exception handling,
    no filtering, no deduplication, and no interpretation of the results.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    manager: HealthManager

    def run(self) -> tuple[bool, ...]:
        checks = self.manager.checks()
        return tuple(check.check() for check in checks)
