from app.application.command_bus.command_bus import CommandBus
from app.application.command_bus.command_request import CommandRequest
from app.application.command_bus.command_result import CommandResult


class CommandBusService:
    """Thin delegation wrapper around CommandBus — `execute()` only
    forwards to the injected CommandBus and returns exactly what it
    returns. It knows exclusively CommandBus.
    """

    def __init__(self, command_bus: CommandBus) -> None:
        self._command_bus = command_bus

    def execute(self, request: CommandRequest) -> CommandResult:
        return self._command_bus.execute(request)
