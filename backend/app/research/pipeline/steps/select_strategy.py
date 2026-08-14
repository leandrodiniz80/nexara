from typing import ClassVar

from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.pipeline.strategy_kind import StrategyKind
from app.research.strategies.search_by_city_strategy import SearchByCityStrategy
from app.research.strategies.search_by_cnae_strategy import SearchByCNAEStrategy
from app.research.strategies.search_by_segment_strategy import SearchBySegmentStrategy
from app.research.strategies.search_nearby_strategy import SearchNearbyStrategy
from app.research.strategies.search_strategy import SearchStrategy

_STRATEGY_CLASSES: dict[StrategyKind, type[SearchStrategy]] = {
    StrategyKind.CITY: SearchByCityStrategy,
    StrategyKind.SEGMENT: SearchBySegmentStrategy,
    StrategyKind.CNAE: SearchByCNAEStrategy,
    StrategyKind.NEARBY: SearchNearbyStrategy,
}


class SelectStrategyStep(PipelineStep):
    """Step 2: instantiates the SearchStrategy matching `context.strategy`. Nothing
    else in the pipeline needs to know the mapping from StrategyKind to a concrete
    class — that knowledge lives only here."""

    name: ClassVar[str] = "select_strategy"

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        state.strategy = _STRATEGY_CLASSES[context.strategy]()
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        state.strategy = None
