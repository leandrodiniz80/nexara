from pydantic import BaseModel, ConfigDict

from app.platform.bootstrap.platform_kernel_facade import PlatformKernelFacade
from app.platform.health.health_coordinator import HealthCoordinator
from app.platform.health.health_report import HealthReport
from app.platform.health.platform_health_facade import PlatformHealthFacade
from app.platform.lifecycle.lifecycle_executor import LifecycleExecutor
from app.platform.lifecycle.lifecycle_manager import LifecycleManager


class PlatformLifecycle(BaseModel):
    """The platform's official lifecycle representation — a frozen model
    holding exactly five collaborators. It runs no domain logic itself
    and knows no concrete implementation of anything beneath `kernel`,
    `lifecycle_manager`, `lifecycle_executor`, `health_coordinator`, or
    `platform_health`. `start()` activates `health_coordinator.coordinate()`
    (discarding its result) followed by `lifecycle_executor.start()`;
    `stop()` activates `lifecycle_executor.stop()`. Each still returns
    exactly what it always returned — `kernel` and `True` respectively —
    never the coordinator's or the executor's own result. `health()`
    delegates exclusively to `platform_health.health()`, with no logic,
    cache, interpretation, or exception handling of its own.
    `lifecycle_manager` merely exists as a collaborator here — nothing in
    this class calls it.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    kernel: PlatformKernelFacade
    lifecycle_manager: LifecycleManager
    lifecycle_executor: LifecycleExecutor
    health_coordinator: HealthCoordinator
    platform_health: PlatformHealthFacade

    def start(self) -> PlatformKernelFacade:
        self.health_coordinator.coordinate()
        self.lifecycle_executor.start()
        return self.kernel

    def stop(self) -> bool:
        self.lifecycle_executor.stop()
        return True

    def restart(self) -> PlatformKernelFacade:
        self.stop()
        return self.start()

    def health(self) -> HealthReport:
        return self.platform_health.health()
