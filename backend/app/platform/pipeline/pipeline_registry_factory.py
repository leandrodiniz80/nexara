from app.platform.pipeline.default_stage_provider import DefaultStageProvider
from app.platform.pipeline.pipeline_registry import PipelineRegistry
from app.platform.pipeline.stage_provider import StageProvider


def build_default_pipeline_registry(
    *, stage_provider: StageProvider | None = None
) -> PipelineRegistry:
    """Composition root for this registry. Knows no concrete PipelineStage
    and no domain at all — it only asks a StageProvider (DefaultStageProvider
    when not given) for whichever stages it supplies, in order, and
    registers them into a PipelineRegistry. Which stages exist, and how
    they're wired, is now exclusively StageProvider's concern.
    """
    provider = stage_provider or DefaultStageProvider()
    return PipelineRegistry().register_many(list(provider.stages()))
