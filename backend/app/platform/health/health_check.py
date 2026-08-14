from abc import ABC, abstractmethod


class HealthCheck(ABC):
    """The contract a future module implements to report its own health.
    This sprint defines the contract only — no concrete check exists yet,
    and nothing calls these methods.
    """

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def check(self) -> bool:
        ...
