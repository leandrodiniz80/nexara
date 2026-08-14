from typing import ClassVar

from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.services.duplicate_detector import DuplicateDetector


class RemoveDuplicatesStep(PipelineStep):
    """Step 6: collapses duplicate groups (DuplicateDetector.find_duplicates() +
    merge()) found among the *valid* results — duplicates are detected after
    normalization/validation so a malformed-email record never gets to "win" a merge
    over a clean one just by coincidence of list order."""

    name: ClassVar[str] = "remove_duplicates"

    def __init__(self, duplicate_detector: DuplicateDetector) -> None:
        self.duplicate_detector = duplicate_detector

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        before = len(state.valid_results)
        groups = self.duplicate_detector.find_duplicates(state.valid_results)
        grouped_ids = {id(result) for group in groups for result in group}
        merged = [self.duplicate_detector.merge(group) for group in groups]
        singles = [result for result in state.valid_results if id(result) not in grouped_ids]

        state.deduplicated_results = merged + singles
        state.duplicates_removed = before - len(state.deduplicated_results)
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        state.deduplicated_results = []
        state.duplicates_removed = 0
