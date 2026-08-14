from app.application.execution.execution_service import ExecutionService
from app.bootstrap.bootstrap import Bootstrap
from app.runtime.engine.runtime_engine import RuntimeEngine


def build_default_execution_service(*, bootstrap: Bootstrap | None = None) -> ExecutionService:
    """Composition root for this facade — the *only* place that decides how
    ExecutionService gets its RuntimeEngine. Unlike every other module's own
    `build_default_*` factory (which builds its Engine directly), this one
    goes through Bootstrap: `Bootstrap()` with no arguments already loads
    PlatformSettings via `load_platform_settings()` (Configuration's own
    composition root) and, on `initialize()`, calls RuntimeEngine's existing
    Factory internally through ModuleLoader — never constructing a
    RuntimeEngine by hand here.

    Routing through Bootstrap (rather than calling
    `build_default_runtime_engine()` directly) means this facade respects
    whatever PlatformSettings says about Runtime — `runtime_enabled=False`
    or `"runtime"` removed from `enabled_modules` means there is no
    RuntimeEngine to hand out, and `bootstrap.locator().get(RuntimeEngine)`
    raises accordingly, exactly as Configuration being "the single source of
    truth" requires.
    """
    bootstrap = bootstrap or Bootstrap()
    if not bootstrap.is_initialized():
        bootstrap.initialize()
    runtime_engine = bootstrap.locator().get(RuntimeEngine)
    return ExecutionService(runtime_engine)
