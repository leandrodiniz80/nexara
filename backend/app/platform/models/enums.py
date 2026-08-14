import enum


class ModuleType(str, enum.Enum):
    """Every kind of module the Platform Kernel knows how to register a
    descriptor for. This is metadata only — registering ModuleType.WORKFLOW does
    not import or touch app.workflows in any way.
    """

    MISSION = "mission"
    RESEARCH = "research"
    AI = "ai"
    OUTREACH = "outreach"
    WORKFLOW = "workflow"
    AUTOMATION = "automation"
    RUNTIME = "runtime"
    CRM = "crm"
    OBSERVABILITY = "observability"
    API = "api"
    APPLICATION = "application"
