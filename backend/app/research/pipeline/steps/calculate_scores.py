from typing import ClassVar

from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.services.score_calculator import ScoreCalculator


class CalculateScoresStep(PipelineStep):
    """Step 7: sets confidence_score on every deduplicated result via ScoreCalculator.
    Runs after dedup (not before) so a merged record's score reflects its *final*
    combined completeness, not whichever half-complete duplicate happened to be scored
    first."""

    name: ClassVar[str] = "calculate_scores"

    def __init__(self, score_calculator: ScoreCalculator) -> None:
        self.score_calculator = score_calculator

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        for result in state.deduplicated_results:
            result.confidence_score = self.score_calculator.calculate(result)
        state.scored_results = state.deduplicated_results
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        for result in state.scored_results:
            result.confidence_score = None
        state.scored_results = []
