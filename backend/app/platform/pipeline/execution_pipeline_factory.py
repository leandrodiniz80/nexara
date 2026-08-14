from app.platform.pipeline.execution_pipeline import ExecutionPipeline
from app.platform.pipeline.pipeline_registry import PipelineRegistry
from app.platform.pipeline.pipeline_registry_factory import build_default_pipeline_registry


def build_default_execution_pipeline(
    *, pipeline_registry: PipelineRegistry | None = None
) -> ExecutionPipeline:
    """Composition root for this pipeline. Knows no concrete PipelineStage
    and no domain at all — it only asks a PipelineRegistry (built via
    `build_default_pipeline_registry()` when not given) for whichever
    stages are already registered, in order, and wires them into an
    ExecutionPipeline. Adding, removing, or reordering stages is now
    exclusively PipelineRegistry's concern.
    """
    registry = pipeline_registry or build_default_pipeline_registry()
    return ExecutionPipeline(registry.list())
