from app.platform.kernel.platform_kernel import PlatformKernel
from app.platform.models.platform_context import PlatformContext
from app.platform.registry.module_registry import ModuleRegistry
from app.platform.repositories.module_repository import ModuleRepository
from app.platform.services.platform_service import PlatformService


class _CountingKernelFactory:
    """A fake kernel_factory that counts how many times it was called — enough to
    prove PlatformService caches the Kernel rather than rebuilding it every call,
    without needing the real build_default_platform_kernel()."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> PlatformKernel:
        self.calls += 1
        return PlatformKernel(
            registry=ModuleRegistry(), repository=ModuleRepository(), context=PlatformContext()
        )


def test_load_kernel_builds_the_kernel_only_once():
    factory = _CountingKernelFactory()
    service = PlatformService(kernel_factory=factory)

    first = service.load_kernel()
    second = service.load_kernel()

    assert first is second
    assert factory.calls == 1


def test_initialize_loads_the_kernel_and_marks_the_service_initialized():
    factory = _CountingKernelFactory()
    service = PlatformService(kernel_factory=factory)

    kernel = service.initialize()

    assert isinstance(kernel, PlatformKernel)
    assert service.status()["initialized"] is True
    assert service.status()["kernel_loaded"] is True


def test_status_before_any_load_reports_not_initialized_and_not_loaded():
    service = PlatformService(kernel_factory=_CountingKernelFactory())

    status = service.status()

    assert status == {"initialized": False, "kernel_loaded": False}


def test_shutdown_resets_initialized_and_kernel_state():
    factory = _CountingKernelFactory()
    service = PlatformService(kernel_factory=factory)
    service.initialize()

    service.shutdown()

    assert service.status() == {"initialized": False, "kernel_loaded": False}


def test_load_kernel_after_shutdown_rebuilds_a_fresh_kernel():
    factory = _CountingKernelFactory()
    service = PlatformService(kernel_factory=factory)
    first = service.initialize()

    service.shutdown()
    second = service.load_kernel()

    assert first is not second
    assert factory.calls == 2
