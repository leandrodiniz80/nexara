from app.operations.module.operations_stage_provider import OperationsStageProvider
from app.platform.modules.platform_module import PlatformModule
from app.platform.pipeline.stage_provider import StageProvider

_MODULE_NAME = "operations"


class OperationsModule(PlatformModule):
    """Operations' own official PlatformModule — the platform's pilot
    migration to the module architecture. Supplies exclusively its own
    OperationsStage via OperationsStageProvider.
    """

    def __init__(self, *, stage_provider: StageProvider | None = None) -> None:
        self._stage_provider = stage_provider or OperationsStageProvider()

    def name(self) -> str:
        return _MODULE_NAME

    def stage_provider(self) -> StageProvider:
        return self._stage_provider
