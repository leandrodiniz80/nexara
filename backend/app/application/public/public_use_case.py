from pydantic import BaseModel, ConfigDict


class PublicUseCase(BaseModel):
    """One entry in the platform's public use-case catalog — frozen: a
    plain description of what a future interface (REST, GraphQL, CLI,
    Worker, SDK, Mobile) may invoke, not the invocation itself.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    enabled: bool
