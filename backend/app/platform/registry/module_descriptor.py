from pydantic import BaseModel, ConfigDict


class ModuleDescriptor(BaseModel):
    """Static, self-reported metadata about a platform module — never the module's
    own Engine, just a description of it: its name, version, whether it's enabled,
    a free-form status label, and a human description. Frozen: registering a
    module means handing the Kernel a fresh descriptor, never mutating one that's
    already registered in place.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    enabled: bool = True
    status: str = "stable"
    description: str = ""
