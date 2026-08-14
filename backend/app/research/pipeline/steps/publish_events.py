from datetime import datetime, timezone
from typing import ClassVar

from app.events.publishers.event_publisher import EventPublisher
from app.events.schemas.research_events import ResearchCompleted, ResearchStarted
from app.research.pipeline.average_score import average_score
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep


class PublishEventsStep(PipelineStep):
    """Step 9: publishes ResearchStarted and ResearchCompleted through EventPublisher.

    Both events are emitted here, at the end, rather than ResearchStarted firing back
    at Step 1 — the spec names this single step as responsible for "Publicar:
    ResearchStarted, ResearchCompleted" together. ResearchStarted's own `occurred_at`
    is still backdated to `context.started_at`, so its timestamp is accurate even
    though both events reach the EventBus back-to-back in wall-clock terms.

    This is the one place app.research imports from app.events — publishing through
    the shared, business-agnostic event infrastructure is exactly what that module
    exists for; it is not a dependency on another business module (Mission/Prospect/AI),
    which is what "nenhum módulo pode depender diretamente de outro" actually forbids.
    """

    name: ClassVar[str] = "publish_events"

    def __init__(self, publisher: EventPublisher) -> None:
        self.publisher = publisher

    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        aggregate_id = context.mission_id or context.request_id

        started = ResearchStarted(
            aggregate_id=aggregate_id,
            payload={"strategy": context.strategy.value, "criteria": context.query},
            occurred_at=context.started_at or datetime.now(timezone.utc),
        )
        completed = ResearchCompleted(
            aggregate_id=aggregate_id,
            payload={
                "results_found": len(state.raw_results),
                "duplicates_removed": state.duplicates_removed,
                "average_score": average_score(state.scored_results),
            },
        )

        await self.publisher.publish(started)
        await self.publisher.publish(completed, causation_id=started.event_id)
        state.completed_steps.append(self.name)
        return state

    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        """Events are historical facts once published — there is no "unpublish"."""
