from app.application.execution.execution_result_processor import ExecutionResultProcessor
from app.bootstrap.bootstrap import Bootstrap
from app.crm.engine.crm_engine import CRMEngine
from app.integration.adapters.crm_adapter import CRMAdapter


def build_default_execution_result_processor(
    *, bootstrap: Bootstrap | None = None
) -> ExecutionResultProcessor:
    """Composition root for this processor — mirrors
    execution_service_factory.build_default_execution_service() exactly:
    routes through Bootstrap (which already depends exclusively on
    PlatformSettings) to obtain the real CRMEngine, wraps it in the existing
    CRMAdapter (app.integration.adapters.crm_adapter — reused, never
    reimplemented), and never constructs an Engine by hand.

    Unlike Runtime for ExecutionService, CRM is optional here: if it is
    disabled in PlatformSettings (`crm_enabled=False`, or "crm" removed from
    `enabled_modules`), Bootstrap simply never registered a CRMEngine — this
    factory then builds an ExecutionResultProcessor with no CRMAdapter at
    all, and process() defensively skips CRM registration, exactly as if the
    caller had disabled it explicitly.
    """
    bootstrap = bootstrap or Bootstrap()
    if not bootstrap.is_initialized():
        bootstrap.initialize()
    locator = bootstrap.locator()
    crm_adapter = CRMAdapter(locator.get(CRMEngine)) if locator.has(CRMEngine) else None
    return ExecutionResultProcessor(crm_adapter)
