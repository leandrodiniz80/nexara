from app.platform.modules.composite_stage_provider import CompositeStageProvider
from app.platform.modules.platform_module import PlatformModule
from app.platform.pipeline.stage_provider import StageProvider

_MODULE_NAME = "composite"


class CompositePlatformModule(PlatformModule):
    """The only PlatformModule authorized to know about other
    PlatformModules — it unifies every given module's own StageProvider
    into a single CompositeStageProvider. No individual module (Default,
    Operations, or any future module) ever composes another module itself.
    """

    def __init__(self, modules: list[PlatformModule]) -> None:
        self._stage_provider = CompositeStageProvider(
            [module.stage_provider() for module in modules]
        )

    def name(self) -> str:
        return _MODULE_NAME

    def stage_provider(self) -> StageProvider:
        return self._stage_provider
