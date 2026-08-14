from pydantic import BaseModel, ConfigDict

from app.platform.capabilities.capability_executor import CapabilityExecutor


class PlatformCapabilities(BaseModel):
    """The platform's official public facade for its capability
    subsystem — a frozen model holding exactly one collaborator.
    `capabilities()` delegates exclusively to `executor.execute()` and
    returns exactly what it produced, fresh on every call. No additional
    logic, no transformation, no interpretation, no exception handling.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    executor: CapabilityExecutor

    def capabilities(self) -> tuple[str, ...]:
        return self.executor.execute()
