from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.stage_provider import StageProvider


class CompositeStageProvider(StageProvider):
    """Unifies N StageProviders into one: walks each provider's stages() in
    order, keeping the first stage seen for each distinct name and
    dropping any later stage that repeats a name already seen. Preserves
    the order stages were first encountered across all given providers.
    """

    def __init__(self, stage_providers: list[StageProvider]) -> None:
        self._stage_providers = list(stage_providers)

    def stages(self) -> tuple[PipelineStage, ...]:
        seen_names: set[str] = set()
        unified: list[PipelineStage] = []
        for provider in self._stage_providers:
            for stage in provider.stages():
                if stage.name() in seen_names:
                    continue
                seen_names.add(stage.name())
                unified.append(stage)
        return tuple(unified)
