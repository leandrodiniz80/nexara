from pydantic import BaseModel, ConfigDict, Field

from app.application.commands.application_command import ApplicationCommand
from app.shared.registry.registry import Registry


class CommandRegistry(BaseModel):
    """The platform's frozen, complete list of publicly registered commands
    at one point in time. CommandRegistryService always returns a new one,
    built fresh from ApplicationCatalogService's own catalog — never
    edited in place. `commands` remains the exact same public field it
    always was; register/register_many/find/exists/list are now
    implemented by encapsulating a generic Registry[ApplicationCommand]
    rather than reimplementing the same loop CommandRegistryService,
    QueryRegistry, and ModuleRegistry each used to duplicate.
    """

    model_config = ConfigDict(frozen=True)

    commands: tuple[ApplicationCommand, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[ApplicationCommand]:
        return Registry(items=self.commands, key=lambda command: command.name)

    def register(self, command: ApplicationCommand) -> "CommandRegistry":
        return CommandRegistry(commands=tuple(self._as_registry().register(command).list()))

    def register_many(self, commands: list[ApplicationCommand]) -> "CommandRegistry":
        return CommandRegistry(
            commands=tuple(self._as_registry().register_many(commands).list())
        )

    def find(self, name: str) -> ApplicationCommand | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def list(self) -> list[ApplicationCommand]:
        return self._as_registry().list()
