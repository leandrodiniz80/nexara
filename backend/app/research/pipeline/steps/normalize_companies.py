from typing import ClassVar

from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.services.enrichment_pipeline import EnrichmentPipeline


class NormalizeCompaniesStep(PipelineStep):
    """Step 5: cleans up every raw result (EnrichmentPipeline.normalize()) and drops
    the ones that fail EnrichmentPipeline.validate() — e.g. a malformed email. Each
    drop is recorded as a warning rather than silently vanishing; nothing here is an
    error, since finding some unusable records is a normal, expected outcome of a
    real search.
    """

    name: ClassVar[str] = "normalize_companies"

    def __init__(self, enrichment_pipeline: EnrichmentPipeline) -> None:
        self.enrichment_pipeline = enrichment_pipeline

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        valid_results = []
        for raw in state.raw_results:
            normalized = self.enrichment_pipeline.normalize(raw)
            issues = self.enrichment_pipeline.validate(normalized)
            if issues:
                state.warnings.append(
                    f"Discarded '{normalized.company_name}': {'; '.join(issues)}"
                )
                continue
            valid_results.append(normalized)

        state.valid_results = valid_results
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        state.valid_results = []
