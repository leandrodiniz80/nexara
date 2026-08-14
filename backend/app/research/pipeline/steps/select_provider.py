from typing import ClassVar

from app.research.exceptions.provider_exceptions import ProviderNotAvailableError
from app.research.models.enums import ResearchSource
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.providers.base.research_provider import ResearchProvider


class SelectProviderStep(PipelineStep):
    """Step 3: picks the ResearchProvider matching `context.provider` — or MOCK if the
    context doesn't name one, since this phase only ever runs against Mock providers.

    This is the *only* place that knows which providers exist and which one is the
    default. Swapping the default (e.g. to GoogleMapsProvider once it's implemented)
    or adding a new provider never touches any other step.
    """

    name: ClassVar[str] = "select_provider"

    def __init__(self, providers: dict[ResearchSource, ResearchProvider]) -> None:
        self.providers = providers

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        source = context.provider or ResearchSource.MOCK
        try:
            state.provider = self.providers[source]
        except KeyError as exc:
            raise ProviderNotAvailableError(source.value) from exc
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        state.provider = None
