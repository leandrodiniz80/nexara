from typing import Any, Protocol

from app.ai.orchestrator.ai_orchestrator import AIOrchestrator
from app.ai.services.ai_orchestrator_factory import build_default_orchestrator
from app.application.tasks.base.application_task import ApplicationTask
from app.application.tasks.copy_task import CopyTask
from app.application.tasks.followup_task import FollowupTask
from app.application.tasks.proposal_task import ProposalTask
from app.application.tasks.qualification_task import QualificationTask
from app.application.tasks.registry.task_registry import TaskRegistry
from app.application.tasks.research_task import ResearchTask
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine
from app.research.pipeline.factory import build_default_lead_discovery_pipeline
from app.sales_intelligence.engine.sales_intelligence_engine import SalesIntelligenceEngine
from app.sales_intelligence.services.sales_intelligence_engine_factory import (
    build_default_sales_intelligence_engine,
)


class _SupportsPipelineExecute(Protocol):
    async def execute(self, context: Any) -> Any: ...


class TaskFactory:
    """Builds ApplicationTask instances, wiring each to the existing engine(s) it
    calls into. The one place in this layer that imports each module's own
    composition root by name — every concrete Task class only ever sees the
    already-built collaborator, never a Provider, a database session, or an API
    client.
    """

    def __init__(
        self,
        *,
        ai_orchestrator: AIOrchestrator | None = None,
        outreach_engine: OutreachEngine | None = None,
        lead_discovery_pipeline: _SupportsPipelineExecute | None = None,
        sales_intelligence_engine: SalesIntelligenceEngine | None = None,
    ) -> None:
        self.ai_orchestrator = ai_orchestrator or build_default_orchestrator()
        self.outreach_engine = outreach_engine or build_default_outreach_engine()
        self.lead_discovery_pipeline = (
            lead_discovery_pipeline or build_default_lead_discovery_pipeline()
        )
        self.sales_intelligence_engine = (
            sales_intelligence_engine or build_default_sales_intelligence_engine()
        )

    def build_research_task(self) -> ResearchTask:
        return ResearchTask(self.lead_discovery_pipeline)

    def build_copy_task(self) -> CopyTask:
        return CopyTask(self.ai_orchestrator, self.outreach_engine)

    def build_qualification_task(self) -> QualificationTask:
        return QualificationTask(self.sales_intelligence_engine)

    def build_proposal_task(self) -> ProposalTask:
        return ProposalTask(self.outreach_engine)

    def build_followup_task(self) -> FollowupTask:
        return FollowupTask(self.outreach_engine)

    def build_all(self) -> list[ApplicationTask]:
        return [
            self.build_research_task(),
            self.build_copy_task(),
            self.build_qualification_task(),
            self.build_proposal_task(),
            self.build_followup_task(),
        ]


def build_default_task_registry(factory: TaskFactory | None = None) -> TaskRegistry:
    """Composition root for the whole Application Task layer: builds every task type
    via TaskFactory and registers them, ready to look up by TaskType.
    """
    factory = factory or TaskFactory()
    registry = TaskRegistry()
    for task in factory.build_all():
        registry.register(task)
    return registry
