import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.platform.models.enums import ModuleType
from app.platform.registry.module_descriptor import ModuleDescriptor


class PlatformModule(BaseModel):
    """One registered platform module — the pairing of a ModuleType with the
    ModuleDescriptor it was registered with, plus when that registration happened.
    A bare ModuleDescriptor doesn't know which ModuleType slot it fills; this is
    what PlatformKernel.register_module() actually produces and what ModuleRegistry
    /ModuleRepository store. Frozen, same reasoning as ModuleDescriptor itself:
    assigning a module a new descriptor means registering a new PlatformModule,
    not mutating this one in place.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    module_type: ModuleType
    descriptor: ModuleDescriptor
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
