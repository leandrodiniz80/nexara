from pydantic import BaseModel, ConfigDict


class ApplicationOperation(BaseModel):
    """One discoverable public operation of the platform — frozen: a plain
    description for future consumers (API, CLI, SDK, Dashboard, Workers,
    Scheduler, GraphQL) to browse, never the operation itself and never
    something that executes anything.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    description: str
    category: str
    enabled: bool
