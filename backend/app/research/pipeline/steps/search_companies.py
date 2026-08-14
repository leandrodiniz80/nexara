from typing import ClassVar

from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep


class SearchCompaniesStep(PipelineStep):
    """Step 4: runs `state.strategy.execute(state.provider, **context.query)`. This
    step doesn't know which strategy or provider it's calling — only that both
    conform to their own interfaces (SearchStrategy / ResearchProvider). That's what
    lets SelectStrategy/SelectProvider be swapped without touching this class.
    """

    name: ClassVar[str] = "search_companies"

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        assert state.strategy is not None, "SelectStrategyStep must run before this step"
        assert state.provider is not None, "SelectProviderStep must run before this step"

        state.raw_results = await state.strategy.execute(state.provider, **context.query)
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        state.raw_results = []
