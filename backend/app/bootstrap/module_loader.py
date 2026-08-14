import enum
from typing import Callable

from app.bootstrap.builders import PlatformBuilders


class BootstrapModule(str, enum.Enum):
    """Every platform module Bootstrap knows how to construct. Mission, API,
    Events, and Orchestrator are deliberately absent: Mission/API/Events have
    no single composition-root Factory returning one top-level engine today,
    and Orchestrator's `build_orchestrator()` requires four real
    DecisionPort/RulesPort/RuntimePort/ObservabilityPort adapters — wiring
    those would itself be the kind of module integration this sprint does not
    do. A future sprint can extend this enum once those exist.
    """

    AI = "ai"
    RESEARCH = "research"
    OUTREACH = "outreach"
    APPLICATION = "application"
    WORKFLOW = "workflow"
    AUTOMATION = "automation"
    RUNTIME = "runtime"
    CRM = "crm"
    DECISION = "decision"
    BUSINESS_RULES = "business_rules"
    OBSERVABILITY = "observability"
    PLATFORM = "platform"
    JOBS = "jobs"
    SALES_INTELLIGENCE = "sales_intelligence"


class ModuleLoader:
    """Knows, for each BootstrapModule, which PlatformBuilders method builds
    it. This is a plain data-driven dispatch table — it never constructs a
    module by hand, only ever calls an existing Factory (through
    PlatformBuilders) exactly once per requested module.
    """

    _LOADERS: dict[BootstrapModule, Callable[[], object]] = {
        BootstrapModule.AI: PlatformBuilders.build_ai,
        BootstrapModule.RESEARCH: PlatformBuilders.build_research,
        BootstrapModule.OUTREACH: PlatformBuilders.build_outreach,
        BootstrapModule.APPLICATION: PlatformBuilders.build_application,
        BootstrapModule.WORKFLOW: PlatformBuilders.build_workflow,
        BootstrapModule.AUTOMATION: PlatformBuilders.build_automation,
        BootstrapModule.RUNTIME: PlatformBuilders.build_runtime,
        BootstrapModule.CRM: PlatformBuilders.build_crm,
        BootstrapModule.DECISION: PlatformBuilders.build_decision,
        BootstrapModule.BUSINESS_RULES: PlatformBuilders.build_business_rules,
        BootstrapModule.OBSERVABILITY: PlatformBuilders.build_observability,
        BootstrapModule.PLATFORM: PlatformBuilders.build_platform,
        BootstrapModule.JOBS: PlatformBuilders.build_jobs,
        BootstrapModule.SALES_INTELLIGENCE: PlatformBuilders.build_sales_intelligence,
    }

    def load(self, module: BootstrapModule) -> object:
        return self._LOADERS[module]()

    def load_modules(self, modules: list[BootstrapModule]) -> dict[BootstrapModule, object]:
        return {module: self.load(module) for module in modules}

    @staticmethod
    def all_modules() -> list[BootstrapModule]:
        return list(BootstrapModule)
