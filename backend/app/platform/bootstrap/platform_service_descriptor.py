from typing import Any

from pydantic import BaseModel, ConfigDict


class PlatformServiceDescriptor(BaseModel):
    """One service PlatformBootstrap has published — frozen. `instance` is
    genuinely `Any`: this descriptor never inspects or transforms it, only
    pairs it with the name PlatformServiceRegistry looks it up by.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    instance: Any
