from pydantic import BaseModel, ConfigDict, Field

from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor


class PlatformServiceCatalog(BaseModel):
    """An immutable, read-only view over already-existing
    PlatformServiceDescriptors — a frozen model holding exactly one
    collaborator collection. It never resolves, builds, or caches a
    service, and knows nothing about any of the layers a descriptor may
    have come from: it only exposes the descriptors it was constructed
    with. The field is named `descriptors` — not `services` — purely to
    avoid colliding with the `services()` method that fulfils this
    class's public contract.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    descriptors: tuple[PlatformServiceDescriptor, ...] = Field(default_factory=tuple)

    def services(self) -> list[PlatformServiceDescriptor]:
        return list(self.descriptors)

    def find(self, name: str) -> PlatformServiceDescriptor | None:
        for descriptor in self.descriptors:
            if descriptor.name == name:
                return descriptor
        return None

    def exists(self, name: str) -> bool:
        return self.find(name) is not None
