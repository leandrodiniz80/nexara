import pytest
from pydantic import ValidationError

from app.config.constants import Environment, LogLevel, ModuleName
from app.config.settings import PlatformSettings


def test_default_construction_matches_the_documented_defaults():
    settings = PlatformSettings()

    assert settings.environment == Environment.DEVELOPMENT
    assert settings.debug is False
    assert settings.application_name == "Elevel Prospect AI"
    assert settings.application_version == "0.1.0"
    assert settings.api_version == "v1"
    assert settings.default_timeout == 30.0
    assert settings.default_language == "pt-BR"
    assert settings.default_timezone == "America/Sao_Paulo"
    assert settings.log_level == LogLevel.INFO
    assert set(settings.enabled_modules) == set(ModuleName)


def test_settings_is_frozen():
    settings = PlatformSettings()

    with pytest.raises(ValidationError):
        settings.debug = True


def test_from_dict_builds_an_equivalent_settings_object():
    raw = {
        "environment": "production",
        "debug": True,
        "application_name": "Elevel Prospect AI",
        "application_version": "1.2.3",
        "database_url": "postgresql://localhost/elevel",
        "api_version": "v2",
        "enabled_modules": ["crm", "runtime"],
        "default_timeout": 45,
        "default_language": "en-US",
        "default_timezone": "UTC",
        "default_ai_provider": "openai",
        "default_llm": "gpt-4",
        "log_level": "debug",
        "worker_enabled": True,
        "scheduler_enabled": True,
        "observability_enabled": True,
        "crm_enabled": True,
        "runtime_enabled": True,
        "workflow_enabled": False,
        "automation_enabled": False,
    }

    settings = PlatformSettings.from_dict(raw)

    assert settings.environment == Environment.PRODUCTION
    assert settings.debug is True
    assert settings.application_version == "1.2.3"
    assert settings.enabled_modules == (ModuleName.CRM, ModuleName.RUNTIME)
    assert settings.default_timeout == 45.0
    assert settings.log_level == LogLevel.DEBUG
    assert settings.workflow_enabled is False


def test_enabled_modules_accepts_raw_strings_and_coerces_to_module_name():
    settings = PlatformSettings(enabled_modules=["ai", "workflow"])

    assert settings.enabled_modules == (ModuleName.AI, ModuleName.WORKFLOW)
