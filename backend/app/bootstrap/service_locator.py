from typing import TypeVar

from app.bootstrap.container import DependencyContainer

T = TypeVar("T")


class ServiceLocator:
    """A read-only view over a DependencyContainer — get()/has()/list_types()
    only, never register(). Once Bootstrap.initialize() hands one out, nothing
    downstream (CLI, API, Worker, Scheduler) can add or replace a service
    through it: this class simply has no method that could — "read-only" here
    means "the capability doesn't exist", not "an exception would be raised".
    """

    def __init__(self, container: DependencyContainer) -> None:
        self._container = container

    def get(self, service_type: type[T]) -> T:
        return self._container.get(service_type)

    def has(self, service_type: type) -> bool:
        return self._container.has(service_type)

    def list_types(self) -> list[type]:
        return self._container.list_types()
