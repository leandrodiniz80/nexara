import abc
from typing import Any


class CommandHandler(abc.ABC):
    """The abstract contract every future Command Handler must implement.
    No concrete implementation exists in this sprint — only the shape a
    handler must have to be registered in HandlerRegistry.
    """

    @abc.abstractmethod
    def command_name(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def handle(self, payload: Any) -> Any:
        raise NotImplementedError
