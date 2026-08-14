import time
from datetime import datetime, timezone

from app.research.pipeline.average_score import average_score
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_report import PipelineReport
from app.research.pipeline.pipeline_result import PipelineResult
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep


class LeadDiscoveryPipeline:
    """Runs the 9 PipelineSteps in sequence and turns what they produced into a
    PipelineReport. This class knows the *order* of the steps and nothing about how
    any one of them works — swapping, reordering or adding a step never requires
    changing this class (Open/Closed); it depends only on the PipelineStep interface
    (Dependency Inversion), never a concrete step.

    If a step raises, every step that already completed gets its rollback() called, in
    reverse order, before the failure is reported — this pipeline never leaves the
    world half-changed (e.g. results persisted but no event published) without at
    least trying to undo it.
    """

    def __init__(self, steps: list[PipelineStep]) -> None:
        self.steps = steps

    async def execute(self, context: PipelineContext) -> PipelineReport:
        context.started_at = datetime.now(timezone.utc)
        state = PipelineState()
        completed_steps: list[PipelineStep] = []
        clock_start = time.perf_counter()

        try:
            for step in self.steps:
                state = await step.execute(context, state)
                completed_steps.append(step)
        except Exception as exc:
            errors = [str(exc)]
            for step in reversed(completed_steps):
                try:
                    await step.rollback(context, state)
                except Exception as rollback_exc:
                    # a failing rollback must not hide the original error
                    errors.append(f"rollback of '{step.name}' also failed: {rollback_exc}")
            context.finished_at = datetime.now(timezone.utc)
            return PipelineReport(
                steps=state.completed_steps,
                duration=time.perf_counter() - clock_start,
                warnings=state.warnings,
                errors=errors,
                statistics={},
                result=None,
            )

        context.finished_at = datetime.now(timezone.utc)
        duration = time.perf_counter() - clock_start
        assert state.provider is not None  # SelectProviderStep always runs before this point

        result = PipelineResult(
            total_found=len(state.raw_results),
            total_valid=len(state.valid_results),
            duplicates_removed=state.duplicates_removed,
            average_score=average_score(state.scored_results),
            execution_time=duration,
            provider_used=state.provider.source,
            strategy_used=context.strategy,
            companies=state.scored_results,
        )
        return PipelineReport(
            steps=state.completed_steps,
            duration=duration,
            warnings=state.warnings,
            errors=[],
            statistics=result.model_dump(mode="json", exclude={"companies"}),
            result=result,
        )
