from typing import Any, Callable

from app.platform.kernel.kernel_factory import build_default_platform_kernel
from app.platform.kernel.platform_kernel import PlatformKernel


class PlatformService:
    """Thin lifecycle wrapper around a PlatformKernel — builds it once and
    remembers whether it's initialized, so Bootstrap/CLI/API/Workers/Scheduler
    each don't have to reimplement that bookkeeping themselves. It runs no
    business rule of its own; it only manages *when* a Kernel exists.
    """

    def __init__(
        self, kernel_factory: Callable[[], PlatformKernel] = build_default_platform_kernel
    ) -> None:
        self._kernel_factory = kernel_factory
        self._kernel: PlatformKernel | None = None
        self._initialized = False

    def load_kernel(self) -> PlatformKernel:
        if self._kernel is None:
            self._kernel = self._kernel_factory()
        return self._kernel

    def initialize(self) -> PlatformKernel:
        kernel = self.load_kernel()
        self._initialized = True
        return kernel

    def shutdown(self) -> None:
        self._initialized = False
        self._kernel = None

    def status(self) -> dict[str, Any]:
        return {
            "initialized": self._initialized,
            "kernel_loaded": self._kernel is not None,
        }
