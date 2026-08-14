from app.application.bus.bus_execution_service_factory import build_default_bus_execution_service
from app.application.command_bus.command_bus import CommandBus
from app.application.command_bus.command_bus_service import CommandBusService
from app.application.commands.command_registry_service_factory import (
    build_default_command_registry_service,
)
from app.application.handlers.handler_registry_service_factory import (
    build_default_handler_registry_service,
)


def build_default_command_bus_service() -> CommandBusService:
    """Composition root for this service. Builds CommandRegistryService,
    HandlerRegistryService, and BusExecutionService exclusively through
    their own official factories, wires them into a CommandBus, and wraps
    that in a CommandBusService — nothing else. HandlerRegistryService's
    own factory still registers no handlers this sprint, so every
    dispatched command resolves to "Handler not registered." until a
    future sprint registers concrete handlers.
    """
    command_bus = CommandBus(
        command_registry_service=build_default_command_registry_service(),
        handler_registry_service=build_default_handler_registry_service(),
        bus_execution_service=build_default_bus_execution_service(),
    )
    return CommandBusService(command_bus)
