from app.application.catalog.application_catalog_service import ApplicationCatalogService
from app.application.catalog.application_operation import ApplicationOperation
from app.application.commands.application_command import ApplicationCommand
from app.application.commands.command_registry import CommandRegistry


class CommandRegistryService:
    """The platform's official registry of public commands — pure
    description, nothing else: it never executes a command, never
    integrates with anything, never knows the internal domain. It knows
    exclusively ApplicationCatalogService — not CRM, not Runtime, not
    Workflow, not Presentation, not Contracts, not PlatformInterface, not
    ApplicationInterfaceService, not PublicUseCaseService.

    `build_registry()` never assembles its list by hand: every
    ApplicationCommand comes from converting one ApplicationOperation
    already returned by ApplicationCatalogService.build_catalog().
    """

    def __init__(self, application_catalog_service: ApplicationCatalogService) -> None:
        self._application_catalog_service = application_catalog_service

    def build_registry(self) -> CommandRegistry:
        catalog = self._application_catalog_service.build_catalog()
        commands = tuple(self._to_command(operation) for operation in catalog.operations)
        return CommandRegistry(commands=commands)

    def list_commands(self) -> tuple[ApplicationCommand, ...]:
        return self.build_registry().commands

    def find(self, name: str) -> ApplicationCommand | None:
        for command in self.list_commands():
            if command.name == name:
                return command
        return None

    def exists(self, name: str) -> bool:
        return self.find(name) is not None

    @staticmethod
    def _to_command(operation: ApplicationOperation) -> ApplicationCommand:
        return ApplicationCommand(
            name=operation.name,
            description=operation.description,
            enabled=operation.enabled,
            operation_name=operation.name,
        )
