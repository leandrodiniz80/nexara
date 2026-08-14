from abc import ABC, abstractmethod


class Feature(ABC):
    """The contract a future platform feature implements. This sprint
    defines the contract only — no feature is ever executed or
    discovered; nothing calls these methods beyond registration.
    """

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def enabled(self) -> bool:
        ...
