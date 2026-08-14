from app.platform.modules.module_registry import ModuleRegistry
from app.platform.modules.module_registry_factory import build_default_module_registry
from app.platform.orchestration.platform_execution_orchestrator import (
    PlatformExecutionOrchestrator,
)
from app.platform.pipeline.execution_pipeline import ExecutionPipeline
from app.platform.pipeline.execution_pipeline_factory import build_default_execution_pipeline
from app.platform.pipeline.pipeline_registry_factory import build_default_pipeline_registry
from app.platform.session.execution_session_factory import build_default_execution_session_service
from app.platform.session.execution_session_service import ExecutionSessionService


def build_default_platform_execution_orchestrator(
    *,
    execution_pipeline: ExecutionPipeline | None = None,
    execution_session_service: ExecutionSessionService | None = None,
    module_registry: ModuleRegistry | None = None,
) -> PlatformExecutionOrchestrator:
    """Composition root for this orchestrator. When no ExecutionPipeline is
    given, it's built by walking the module flow: a ModuleRegistry
    (`build_default_module_registry()` when not given) composites every
    module it holds via `registry.composite()`, whose own stage provider
    feeds `build_default_pipeline_registry()`, which in turn feeds
    `build_default_execution_pipeline()`. The only new collaborator this
    factory knows is ModuleRegistry — which concrete stages exist, and how
    multiple modules combine, stays exclusively ModuleRegistry's and each
    module's own concern. execution_session_service is still built via its
    own official factory, `build_default_execution_session_service()`.
    """
    if execution_pipeline is None:
        registry = module_registry or build_default_module_registry()
        module = registry.composite()
        pipeline_registry = build_default_pipeline_registry(
            stage_provider=module.stage_provider()
        )
        execution_pipeline = build_default_execution_pipeline(pipeline_registry=pipeline_registry)
    return PlatformExecutionOrchestrator(
        execution_pipeline=execution_pipeline,
        execution_session_service=execution_session_service
        or build_default_execution_session_service(),
    )
