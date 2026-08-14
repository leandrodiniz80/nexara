from pydantic import BaseModel, ConfigDict

from app.application.bus.bus_execution_service import BusExecutionService
from app.application.command_bus.command_execution import CommandExecution
from app.application.command_bus.command_request import CommandRequest
from app.application.command_bus.command_result import CommandResult
from app.application.commands.command_registry_service import CommandRegistryService
from app.application.handlers.handler_registry_service import HandlerRegistryService

_COMMAND_NOT_FOUND_REASON = "Command not found."
_HANDLER_NOT_REGISTERED_REASON = "Handler not registered."


def _to_command_result(execution: CommandExecution) -> CommandResult:
    return CommandResult(
        success=execution.success,
        command_name=execution.command,
        payload=execution.payload,
        reason=execution.reason,
        execution_time=execution.duration,
    )


class CommandBus(BaseModel):
    """The platform's single official dispatch infrastructure for public
    commands — a frozen model holding exactly three collaborators. It
    never executes the domain itself, never instantiates a handler, and
    never knows any concrete handler: it only validates that a requested
    command is registered, validates that a handler for it is registered,
    and delegates to that handler. It knows nothing about CRM, Runtime,
    Workflow, Presentation, Contracts, PlatformInterface,
    ApplicationInterfaceService, ApplicationCatalogService,
    PublicUseCaseService, or QueryBus — exclusively CommandRegistryService,
    HandlerRegistryService, and BusExecutionService.

    `execute()` no longer builds CommandExecution's timing fields itself:
    it delegates start/finish entirely to BusExecutionService (shared with
    QueryBus), wraps the resulting BusExecution in a CommandExecution
    (this bus's own internal record, never exposed outside it), then
    builds the CommandResult it returns — with identical values to before
    this shared infrastructure existed.

    This is a deliberate migration away from PublicUseCaseService: with no
    handler registered yet (HandlerRegistryService's registry stays empty
    this sprint), every command now resolves to
    `success=False, reason="Handler not registered."` — not a regression,
    the expected state until concrete handlers are registered in a future
    sprint.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    command_registry_service: CommandRegistryService
    handler_registry_service: HandlerRegistryService
    bus_execution_service: BusExecutionService

    def execute(self, request: CommandRequest) -> CommandResult:
        start = self.bus_execution_service.start(request.command_name)

        if not self.command_registry_service.exists(request.command_name):
            return _to_command_result(
                CommandExecution(
                    bus_execution=self.bus_execution_service.finish(
                        start, success=False, payload=None, reason=_COMMAND_NOT_FOUND_REASON
                    )
                )
            )

        if not self.handler_registry_service.exists(request.command_name):
            return _to_command_result(
                CommandExecution(
                    bus_execution=self.bus_execution_service.finish(
                        start, success=False, payload=None, reason=_HANDLER_NOT_REGISTERED_REASON
                    )
                )
            )

        handler = self.handler_registry_service.find(request.command_name)
        response = handler.handle(request.payload)

        return _to_command_result(
            CommandExecution(
                bus_execution=self.bus_execution_service.finish(
                    start, success=True, payload=response, reason=None
                )
            )
        )
