from typing import TypeVar

T = TypeVar("T")


class ServiceNotRegisteredError(Exception):
    """Raised when DependencyContainer.get() is asked for a type nothing was
    ever registered under."""

    def __init__(self, service_type: type) -> None:
        self.service_type = service_type
        super().__init__(f"No instance registered for type '{service_type.__name__}'.")


class DependencyContainer:
    """Holds one constructed instance per registered type — the platform's
    single "type -> the one instance of it" map. It never constructs anything
    itself: every instance it holds was already built by an existing module
    Factory (via ModuleLoader) before being handed to `register()`.
    """

    def __init__(self) -> None:
        self._instances: dict[type, object] = {}

    def register(self, instance: object, *, as_type: type | None = None) -> None:
        key = as_type or type(instance)
        self._instances[key] = instance

    def get(self, service_type: type[T]) -> T:
        instance = self._instances.get(service_type)
        if instance is None:
            raise ServiceNotRegisteredError(service_type)
        return instance

    def has(self, service_type: type) -> bool:
        return service_type in self._instances

    def list_types(self) -> list[type]:
        return list(self._instances.keys())
