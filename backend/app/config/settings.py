from typing import Any

from pydantic import BaseModel, ConfigDict

from app.config.constants import Environment, LogLevel, ModuleName


class PlatformSettings(BaseModel):
    """The platform's fully-resolved, validated configuration — immutable,
    intended to be loaded exactly once (via configuration.load_platform_settings())
    and passed around from then on, never mutated or reloaded mid-process.
    """

    model_config = ConfigDict(frozen=True)

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    application_name: str = "Elevel Prospect AI"
    application_version: str = "0.1.0"
    database_url: str = "sqlite:///./elevel.db"
    api_version: str = "v1"
    enabled_modules: tuple[ModuleName, ...] = tuple(ModuleName)
    default_timeout: float = 30.0
    default_language: str = "pt-BR"
    default_timezone: str = "America/Sao_Paulo"
    default_ai_provider: str = "mock"
    default_llm: str = "mock-llm"
    log_level: LogLevel = LogLevel.INFO
    worker_enabled: bool = False
    scheduler_enabled: bool = False
    observability_enabled: bool = True
    crm_enabled: bool = True
    runtime_enabled: bool = True
    workflow_enabled: bool = True
    automation_enabled: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PlatformSettings":
        return cls(**raw)
