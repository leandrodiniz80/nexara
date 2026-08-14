from pydantic import BaseModel, ConfigDict

from app.platform.capabilities.capability_manager import CapabilityManager


class CapabilityExecutor(BaseModel):
    """The platform's official infrastructure for running the registered
    Capabilities — a frozen model holding exactly one collaborator.
    `execute()` walks `manager.capabilities()` in order, calls
    `description()` on each, and returns those results as a tuple in the
    same order. No exception handling, no filtering, no deduplication, no
    discovery.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    manager: CapabilityManager

    def execute(self) -> tuple[str, ...]:
        capabilities = self.manager.capabilities()
        return tuple(capability.description() for capability in capabilities)
