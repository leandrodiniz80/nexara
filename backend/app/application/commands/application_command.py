from pydantic import BaseModel, ConfigDict


class ApplicationCommand(BaseModel):
    """One publicly registered command of the platform — frozen: a plain
    description for the future Command Bus to look up, never the command's
    execution itself.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    enabled: bool
    operation_name: str
