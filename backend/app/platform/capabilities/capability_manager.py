from pydantic import BaseModel, ConfigDict

from app.platform.capabilities.capability import Capability
from app.platform.capabilities.capability_registry import CapabilityRegistry


class CapabilityManager(BaseModel):
    """An intermediate layer over CapabilityRegistry — a frozen model
    holding exactly one collaborator. It never runs or discovers a
    capability, and never caches or memoizes anything itself: every
    method is a direct, single-line delegation to `registry`, nothing
    more.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    registry: CapabilityRegistry

    def capability(self, name: str) -> Capability | None:
        return self.registry.find(name)

    def exists(self, name: str) -> bool:
        return self.registry.exists(name)

    def capabilities(self) -> list[Capability]:
        return self.registry.list()
