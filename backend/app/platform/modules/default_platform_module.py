from app.platform.modules.platform_module import PlatformModule
from app.platform.pipeline.default_stage_provider import DefaultStageProvider
from app.platform.pipeline.stage_provider import StageProvider

_DEFAULT_MODULE_NAME = "default"


class DefaultPlatformModule(PlatformModule):
    """The platform's own built-in module: supplies DefaultStageProvider
    (the four official Operations/Decision/Runtime/Observability stages).
    Represents exactly one module — it knows no other PlatformModule and
    performs no composition; combining it with other modules is exclusively
    ModuleRegistry's concern via `composite()`.
    """

    def __init__(self, *, stage_provider: StageProvider | None = None) -> None:
        self._stage_provider = stage_provider or DefaultStageProvider()

    def name(self) -> str:
        return _DEFAULT_MODULE_NAME

    def stage_provider(self) -> StageProvider:
        return self._stage_provider
