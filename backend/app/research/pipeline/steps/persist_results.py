from typing import ClassVar

from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.repositories.research_result_repository import ResearchResultRepository


class PersistResultsStep(PipelineStep):
    """Step 8: saves the scored results into ResearchResultRepository — the only
    persistence this pipeline is allowed to touch, per spec. In-memory today (no
    migration exists for Research Engine); swapping in a DB-backed repository later
    only means changing what gets injected here, not this class.
    """

    name: ClassVar[str] = "persist_results"

    def __init__(self, repository: ResearchResultRepository) -> None:
        self.repository = repository

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        state.persisted_results = self.repository.add_many(state.scored_results)
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        self.repository.remove_many(state.persisted_results)
        state.persisted_results = []
