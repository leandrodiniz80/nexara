from pydantic import BaseModel, ConfigDict, Field

from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor
from app.shared.registry.registry import Registry


class PlatformServiceRegistry(BaseModel):
    """The platform's frozen registry of services published by
    PlatformBootstrap — pure lookup, nothing else. It never builds a
    service itself, never knows any concrete service's domain, and never
    mutates in place. Implemented exclusively by encapsulating a generic
    Registry[PlatformServiceDescriptor] — no reimplementation of
    register/register_many/find/exists/list.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    descriptors: tuple[PlatformServiceDescriptor, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[PlatformServiceDescriptor]:
        return Registry(items=self.descriptors, key=lambda descriptor: descriptor.name)

    def register(self, descriptor: PlatformServiceDescriptor) -> "PlatformServiceRegistry":
        return PlatformServiceRegistry(
            descriptors=tuple(self._as_registry().register(descriptor).list())
        )

    def register_many(
        self, descriptors: list[PlatformServiceDescriptor]
    ) -> "PlatformServiceRegistry":
        return PlatformServiceRegistry(
            descriptors=tuple(self._as_registry().register_many(descriptors).list())
        )

    def find(self, name: str) -> PlatformServiceDescriptor | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def list(self) -> list[PlatformServiceDescriptor]:
        return self._as_registry().list()
