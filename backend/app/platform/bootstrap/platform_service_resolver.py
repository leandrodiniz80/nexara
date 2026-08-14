from typing import Any

from pydantic import BaseModel, ConfigDict

from app.platform.bootstrap.platform_service_registry import PlatformServiceRegistry


class PlatformServiceResolver(BaseModel):
    """The platform's single official service resolver — a frozen model
    holding exactly one collaborator. It never constructs anything itself
    and knows no concrete implementation of anything it resolves: it only
    asks the PlatformServiceRegistry it was given whether a published
    service exists and, when it does, returns exactly the instance
    already published for it.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    registry: PlatformServiceRegistry

    def resolve(self, name: str) -> Any:
        descriptor = self.registry.find(name)
        if descriptor is None:
            raise KeyError(name)
        return descriptor.instance

    def exists(self, name: str) -> bool:
        return self.registry.exists(name)

    def list(self) -> list:
        return self.registry.list()
