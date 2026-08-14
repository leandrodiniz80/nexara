from pydantic import BaseModel, ConfigDict


class ApplicationQuery(BaseModel):
    """One publicly registered query of the platform — frozen: a plain
    description for the future QueryBus to look up, never the query's
    execution itself.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    enabled: bool
    operation_name: str
