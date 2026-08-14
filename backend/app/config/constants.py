import enum


class Environment(str, enum.Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ModuleName(str, enum.Enum):
    """Every platform module the configuration system knows the name of — its
    own list, intentionally not shared with app.bootstrap.module_loader's
    BootstrapModule: app.config must stay completely decoupled from every
    other module, including app.bootstrap.
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


DEFAULT_ENVIRONMENT = Environment.DEVELOPMENT
DEFAULT_DEBUG = False
DEFAULT_APPLICATION_NAME = "Elevel Prospect AI"
DEFAULT_APPLICATION_VERSION = "0.1.0"
DEFAULT_DATABASE_URL = "sqlite:///./elevel.db"
DEFAULT_API_VERSION = "v1"
DEFAULT_ENABLED_MODULES: tuple[ModuleName, ...] = tuple(ModuleName)
DEFAULT_TIMEOUT = 30.0
DEFAULT_LANGUAGE = "pt-BR"
DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_AI_PROVIDER = "mock"
DEFAULT_LLM = "mock-llm"
DEFAULT_LOG_LEVEL = LogLevel.INFO
DEFAULT_WORKER_ENABLED = False
DEFAULT_SCHEDULER_ENABLED = False
DEFAULT_OBSERVABILITY_ENABLED = True
DEFAULT_CRM_ENABLED = True
DEFAULT_RUNTIME_ENABLED = True
DEFAULT_WORKFLOW_ENABLED = True
DEFAULT_AUTOMATION_ENABLED = True
