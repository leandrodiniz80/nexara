from app.platform.bootstrap.platform_kernel_facade_factory import (
    build_default_platform_kernel_facade,
)
from app.platform.health.health_coordinator_factory import build_default_health_coordinator
from app.platform.health.platform_health_facade_factory import (
    build_default_platform_health_facade,
)
from app.platform.lifecycle.lifecycle_executor_factory import build_default_lifecycle_executor
from app.platform.lifecycle.lifecycle_manager_factory import build_default_lifecycle_manager
from app.platform.lifecycle.platform_lifecycle import PlatformLifecycle


def build_default_platform_lifecycle() -> PlatformLifecycle:
    """Composition root for this lifecycle. Builds all five of its
    collaborators exclusively through their own official factories —
    `build_default_platform_kernel_facade()`,
    `build_default_lifecycle_manager()`,
    `build_default_lifecycle_executor()`,
    `build_default_health_coordinator()`, and
    `build_default_platform_health_facade()` — and wires them into a
    PlatformLifecycle — nothing else.
    """
    return PlatformLifecycle(
        kernel=build_default_platform_kernel_facade(),
        lifecycle_manager=build_default_lifecycle_manager(),
        lifecycle_executor=build_default_lifecycle_executor(),
        health_coordinator=build_default_health_coordinator(),
        platform_health=build_default_platform_health_facade(),
    )
