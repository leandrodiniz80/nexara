from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, PrivateAttr

from app.application.command_bus.command_bus_service_factory import (
    build_default_command_bus_service,
)
from app.application.public.public_use_case_service_factory import (
    build_default_public_use_case_service,
)
from app.application.query_bus.query_bus_service_factory import build_default_query_bus_service
from app.interface.platform_interface_factory import build_default_platform_interface
from app.operations.coordinator.operations_coordinator_factory import (
    build_default_operations_coordinator,
)
from app.platform.bootstrap.platform_service_catalog_factory import (
    build_platform_service_catalog,
)
from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor
from app.platform.bootstrap.platform_service_registry import PlatformServiceRegistry
from app.platform.bootstrap.platform_service_resolver_factory import (
    build_default_platform_service_resolver,
)
from app.platform.capabilities.platform_capabilities_factory import (
    build_default_platform_capabilities,
)
from app.platform.events.platform_events_factory import build_default_platform_events
from app.platform.features.platform_features_factory import build_default_platform_features
from app.platform.health.platform_health_facade_factory import (
    build_default_platform_health_facade,
)
from app.platform.lifecycle.platform_lifecycle_factory import build_default_platform_lifecycle
from app.platform.orchestration.platform_execution_orchestrator_factory import (
    build_default_platform_execution_orchestrator,
)
from app.presentation.presentation_facade_factory import build_default_presentation_facade
from app.runtime.services.runtime_engine_factory import build_default_runtime_engine


class PlatformBootstrap(BaseModel):
    """The platform's official Composition Root — a frozen object whose
    single responsibility is assembling the platform's whole dependency
    tree, exclusively through the already-existing official
    `build_default_*` factories. It never executes domain logic, never
    instantiates a concrete class directly, and never knows any
    implementation beyond which factory to call.

    Every method is lazy, memoized, and singleton within one
    PlatformBootstrap instance: the first call builds via the official
    factory and caches the result; every later call on the same instance
    returns that exact same object. A different PlatformBootstrap instance
    always starts with an empty cache of its own.
    """

    model_config = ConfigDict(frozen=True)

    _cache: dict[str, Any] = PrivateAttr(default_factory=dict)

    def _get_or_build(self, key: str, factory: Callable[[], Any]) -> Any:
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

    def runtime(self) -> Any:
        return self._get_or_build("runtime", build_default_runtime_engine)

    def operations(self) -> Any:
        return self._get_or_build("operations", build_default_operations_coordinator)

    def command_bus(self) -> Any:
        return self._get_or_build("command_bus", build_default_command_bus_service)

    def query_bus(self) -> Any:
        return self._get_or_build("query_bus", build_default_query_bus_service)

    def application(self) -> Any:
        return self._get_or_build("application", build_default_public_use_case_service)

    def presentation(self) -> Any:
        return self._get_or_build("presentation", build_default_presentation_facade)

    def platform_interface(self) -> Any:
        return self._get_or_build("platform_interface", build_default_platform_interface)

    def orchestrator(self) -> Any:
        return self._get_or_build(
            "orchestrator", build_default_platform_execution_orchestrator
        )

    def health(self) -> Any:
        return self._get_or_build("health", build_default_platform_health_facade)

    def lifecycle(self) -> Any:
        return self._get_or_build("lifecycle", build_default_platform_lifecycle)

    def events(self) -> Any:
        return self._get_or_build("events", build_default_platform_events)

    def capabilities(self) -> Any:
        return self._get_or_build("capabilities", build_default_platform_capabilities)

    def features(self) -> Any:
        return self._get_or_build("features", build_default_platform_features)

    def registry(self) -> Any:
        return self._get_or_build("registry", self._build_registry)

    def resolver(self) -> Any:
        return self._get_or_build("resolver", self._build_resolver)

    def catalog(self) -> Any:
        return self._get_or_build("catalog", self._build_catalog)

    def _build_resolver(self) -> Any:
        return build_default_platform_service_resolver(registry=self.registry())

    def _build_catalog(self) -> Any:
        return build_platform_service_catalog(services=tuple(self.registry().list()))

    def _build_registry(self) -> PlatformServiceRegistry:
        return PlatformServiceRegistry().register_many(
            [
                PlatformServiceDescriptor(name="runtime", instance=self.runtime()),
                PlatformServiceDescriptor(name="operations", instance=self.operations()),
                PlatformServiceDescriptor(name="command_bus", instance=self.command_bus()),
                PlatformServiceDescriptor(name="query_bus", instance=self.query_bus()),
                PlatformServiceDescriptor(name="application", instance=self.application()),
                PlatformServiceDescriptor(name="presentation", instance=self.presentation()),
                PlatformServiceDescriptor(
                    name="platform_interface", instance=self.platform_interface()
                ),
                PlatformServiceDescriptor(name="orchestrator", instance=self.orchestrator()),
                PlatformServiceDescriptor(name="health", instance=self.health()),
                PlatformServiceDescriptor(name="lifecycle", instance=self.lifecycle()),
                PlatformServiceDescriptor(name="events", instance=self.events()),
                PlatformServiceDescriptor(name="capabilities", instance=self.capabilities()),
                PlatformServiceDescriptor(name="features", instance=self.features()),
            ]
        )
