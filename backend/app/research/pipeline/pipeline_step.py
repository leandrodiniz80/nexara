from abc import ABC, abstractmethod
from typing import ClassVar

from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_state import PipelineState


class PipelineStep(ABC):
    """One independently-replaceable stage of the Lead Discovery Pipeline.

    A step only ever sees PipelineContext (the request) and PipelineState (what prior
    steps produced) — never another step's class. That single rule is what makes
    "nenhuma etapa deve conhecer a implementação das demais" hold: LeadDiscoveryPipeline
    can reorder, swap or add steps without any step needing to change.
    """

    name: ClassVar[str]

    @abstractmethod
    async def execute(self, context: PipelineContext, state: PipelineState) -> PipelineState:
        """Do this step's work and return the (possibly updated) state for the next step."""

    @abstractmethod
    async def rollback(self, context: PipelineContext, state: PipelineState) -> None:
        """Undo whatever this step did. Called in reverse order if a *later* step
        raises — steps with no side effect to undo (most of them: everything here is
        an in-memory transformation) implement this as a no-op."""
