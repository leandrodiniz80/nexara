from typing import Any

from app.config.constants import (
    DEFAULT_AI_PROVIDER,
    DEFAULT_API_VERSION,
    DEFAULT_APPLICATION_NAME,
    DEFAULT_APPLICATION_VERSION,
    DEFAULT_AUTOMATION_ENABLED,
    DEFAULT_CRM_ENABLED,
    DEFAULT_DATABASE_URL,
    DEFAULT_DEBUG,
    DEFAULT_ENABLED_MODULES,
    DEFAULT_ENVIRONMENT,
    DEFAULT_LANGUAGE,
    DEFAULT_LLM,
    DEFAULT_LOG_LEVEL,
    DEFAULT_OBSERVABILITY_ENABLED,
    DEFAULT_RUNTIME_ENABLED,
    DEFAULT_SCHEDULER_ENABLED,
    DEFAULT_TIMEOUT,
    DEFAULT_TIMEZONE,
    DEFAULT_WORKER_ENABLED,
    DEFAULT_WORKFLOW_ENABLED,
)


def default_configuration() -> dict[str, Any]:
    """The platform's baseline configuration values — what PlatformSettings
    falls back to when nothing else overrides a field. This is the
    lowest-priority source ConfigurationLoader merges: EnvironmentVariables
    and JSON/YAML file sources, when present, override these key by key.
    """
    return {
        "environment": DEFAULT_ENVIRONMENT.value,
        "debug": DEFAULT_DEBUG,
        "application_name": DEFAULT_APPLICATION_NAME,
        "application_version": DEFAULT_APPLICATION_VERSION,
        "database_url": DEFAULT_DATABASE_URL,
        "api_version": DEFAULT_API_VERSION,
        "enabled_modules": [module.value for module in DEFAULT_ENABLED_MODULES],
        "default_timeout": DEFAULT_TIMEOUT,
        "default_language": DEFAULT_LANGUAGE,
        "default_timezone": DEFAULT_TIMEZONE,
        "default_ai_provider": DEFAULT_AI_PROVIDER,
        "default_llm": DEFAULT_LLM,
        "log_level": DEFAULT_LOG_LEVEL.value,
        "worker_enabled": DEFAULT_WORKER_ENABLED,
        "scheduler_enabled": DEFAULT_SCHEDULER_ENABLED,
        "observability_enabled": DEFAULT_OBSERVABILITY_ENABLED,
        "crm_enabled": DEFAULT_CRM_ENABLED,
        "runtime_enabled": DEFAULT_RUNTIME_ENABLED,
        "workflow_enabled": DEFAULT_WORKFLOW_ENABLED,
        "automation_enabled": DEFAULT_AUTOMATION_ENABLED,
    }
