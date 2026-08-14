from pydantic import BaseModel, ConfigDict, Field

from app.application.handlers.command_handler import CommandHandler


class HandlerRegistry(BaseModel):
    """The platform's frozen, complete list of registered Command Handlers
    at one point in time. HandlerRegistryService always returns a new one,
    built fresh from whatever handlers it was given — never edited in
    place.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    handlers: tuple[CommandHandler, ...] = Field(default_factory=tuple)
