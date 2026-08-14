from pydantic import BaseModel, ConfigDict, Field

from app.platform.capabilities.capability import Capability
from app.shared.registry.registry import Registry


class CapabilityRegistry(BaseModel):
    """The platform's frozen registry of Capabilities — pure lookup,
    nothing else: it never runs a capability, never knows any concrete
    capability's domain, and never mutates in place. Implemented
    exclusively by encapsulating a generic Registry[Capability] — no
    reimplementation of register/register_many/find/exists/list.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    capabilities: tuple[Capability, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[Capability]:
        return Registry(items=self.capabilities, key=lambda capability: capability.name())

    def register(self, capability: Capability) -> "CapabilityRegistry":
        return CapabilityRegistry(
            capabilities=tuple(self._as_registry().register(capability).list())
        )

    def register_many(self, capabilities: list[Capability]) -> "CapabilityRegistry":
        return CapabilityRegistry(
            capabilities=tuple(self._as_registry().register_many(capabilities).list())
        )

    def find(self, name: str) -> Capability | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def list(self) -> list[Capability]:
        return self._as_registry().list()
