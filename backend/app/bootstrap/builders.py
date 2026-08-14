from app.ai.orchestrator.ai_orchestrator import AIOrchestrator
from app.ai.services.ai_orchestrator_factory import build_default_orchestrator
from app.application.tasks.registry.task_registry import TaskRegistry
from app.application.tasks.task_factory import build_default_task_registry
from app.automation.engine.automation_engine import AutomationEngine
from app.automation.services.automation_engine_factory import build_default_automation_engine
from app.business_rules.engine.rules_engine import RulesEngine
from app.business_rules.engine.rules_engine_factory import build_default_rules_engine
from app.crm.engine.crm_engine import CRMEngine
from app.crm.services.crm_engine_factory import build_default_crm_engine
from app.decision.engine.decision_engine import DecisionEngine
from app.decision.engine.decision_engine_factory import build_default_decision_engine
from app.jobs.engine.job_engine import JobEngine
from app.jobs.services.job_engine_factory import build_default_job_engine
from app.observability.engine.observability_engine import ObservabilityEngine
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine
from app.platform.kernel.kernel_factory import build_default_platform_kernel
from app.platform.kernel.platform_kernel import PlatformKernel
from app.research.engine.research_engine import ResearchEngine
from app.research.services.research_engine_factory import build_default_research_engine
from app.runtime.engine.runtime_engine import RuntimeEngine
from app.runtime.services.runtime_engine_factory import build_default_runtime_engine
from app.sales_intelligence.engine.sales_intelligence_engine import SalesIntelligenceEngine
from app.sales_intelligence.services.sales_intelligence_engine_factory import (
    build_default_sales_intelligence_engine,
)
from app.workflows.engine.workflow_engine import WorkflowEngine
from app.workflows.services.workflow_engine_factory import build_default_workflow_engine


class PlatformBuilders:
    """One method per platform module, each calling that module's own existing
    `build_default_*` Factory with zero arguments — exactly how every other
    caller of these functions already uses them. This is the single place in
    app.bootstrap that imports every module's concrete Engine/Registry type and
    Factory function; ModuleLoader only ever calls these methods by name, never
    the raw Factories directly.

    Nothing here is instantiated by hand: every method is a one-line
    passthrough to a Factory that already existed before this sprint.
    """

    @staticmethod
    def build_ai() -> AIOrchestrator:
        return build_default_orchestrator()

    @staticmethod
    def build_research() -> ResearchEngine:
        return build_default_research_engine()

    @staticmethod
    def build_outreach() -> OutreachEngine:
        return build_default_outreach_engine()

    @staticmethod
    def build_application() -> TaskRegistry:
        return build_default_task_registry()

    @staticmethod
    def build_workflow() -> WorkflowEngine:
        return build_default_workflow_engine()

    @staticmethod
    def build_automation() -> AutomationEngine:
        return build_default_automation_engine()

    @staticmethod
    def build_runtime() -> RuntimeEngine:
        return build_default_runtime_engine()

    @staticmethod
    def build_crm() -> CRMEngine:
        return build_default_crm_engine()

    @staticmethod
    def build_decision() -> DecisionEngine:
        return build_default_decision_engine()

    @staticmethod
    def build_business_rules() -> RulesEngine:
        return build_default_rules_engine()

    @staticmethod
    def build_observability() -> ObservabilityEngine:
        return build_default_observability_engine()

    @staticmethod
    def build_platform() -> PlatformKernel:
        return build_default_platform_kernel()

    @staticmethod
    def build_jobs() -> JobEngine:
        return build_default_job_engine()

    @staticmethod
    def build_sales_intelligence() -> SalesIntelligenceEngine:
        return build_default_sales_intelligence_engine()
