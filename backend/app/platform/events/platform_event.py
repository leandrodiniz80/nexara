from abc import ABC, abstractmethod


class PlatformEvent(ABC):
    """The contract a future platform event implements. This sprint defines
    the contract only — no event is ever dispatched, published, or
    executed; nothing calls these methods beyond registration.
    """

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def payload(self) -> object:
        ...
