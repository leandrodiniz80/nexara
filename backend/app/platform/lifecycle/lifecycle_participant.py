from abc import ABC, abstractmethod


class LifecycleParticipant(ABC):
    """The contract a future module implements to participate in the
    platform's lifecycle. This sprint defines the contract only — no
    concrete participant exists yet, and nothing calls these methods.
    """

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...
