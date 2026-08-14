from app.application.handlers.command_handler import CommandHandler
from app.application.handlers.handler_registry import HandlerRegistry


class HandlerRegistryService:
    """The platform's official registry of Command Handlers — pure
    lookup, nothing else: it never executes a handler, never knows the
    domain, never knows PublicUseCaseService. It receives exclusively the
    tuple of CommandHandler instances it registers.
    """

    def __init__(self, handlers: tuple[CommandHandler, ...]) -> None:
        self._handlers = handlers

    def build_registry(self) -> HandlerRegistry:
        return HandlerRegistry(handlers=self._handlers)

    def list_handlers(self) -> tuple[CommandHandler, ...]:
        return self._handlers

    def find(self, command_name: str) -> CommandHandler | None:
        for handler in self._handlers:
            if handler.command_name() == command_name:
                return handler
        return None

    def exists(self, command_name: str) -> bool:
        return self.find(command_name) is not None
