from abc import ABC, abstractmethod

from app.platform.pipeline.stage_provider import StageProvider


class PlatformModule(ABC):
    """One module of the platform — identified by name, and responsible for
    supplying the StageProvider that knows its own PipelineStages. Nothing
    else about a module's internals is any other platform component's
    concern.
    """

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def stage_provider(self) -> StageProvider:
        ...
