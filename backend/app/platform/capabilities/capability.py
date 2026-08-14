from abc import ABC, abstractmethod


class Capability(ABC):
    """The contract a future platform functionality implements to describe
    itself. This sprint defines the contract only — no capability is ever
    executed or discovered; nothing calls these methods beyond
    registration.
    """

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def description(self) -> str:
        ...
