from typing import ClassVar

from app.research.pipeline.exceptions import PipelineValidationError
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.pipeline.strategy_kind import StrategyKind

_REQUIRED_QUERY_FIELDS: dict[StrategyKind, tuple[str, ...]] = {
    StrategyKind.CITY: ("city",),
    StrategyKind.SEGMENT: ("segment",),
    StrategyKind.CNAE: ("cnae",),
    StrategyKind.NEARBY: ("latitude", "longitude", "radius_km"),
}


class ValidateRequestStep(PipelineStep):
    """Step 1: confirms `context.query` actually has what `context.strategy` needs
    before anything downstream runs — e.g. a CITY search with no `city` key fails
    here, not three steps later inside SearchCompanies."""

    name: ClassVar[str] = "validate_request"

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        required = _REQUIRED_QUERY_FIELDS[context.strategy]
        missing = [field_name for field_name in required if not context.query.get(field_name)]
        if missing:
            raise PipelineValidationError(
                f"strategy '{context.strategy.value}' requires query field(s): {', '.join(missing)}"
            )
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        """Validation has no side effects — nothing to undo."""
