import pytest

from app.config.configuration import load_platform_settings
from app.config.constants import Environment
from app.config.environment import EnvironmentVariablesProvider
from app.config.exceptions import InvalidConfigurationError
from app.config.loader import ConfigurationLoader
from app.config.providers import DefaultConfigurationProvider
from app.config.settings import PlatformSettings


def test_load_platform_settings_with_no_arguments_never_raises():
    settings = load_platform_settings()

    assert isinstance(settings, PlatformSettings)


def test_backward_compatibility_default_settings_match_platform_settings_defaults():
    """The whole point of "Bootstrap continuará funcionando exatamente como
    hoje caso nada seja informado": loading configuration from nothing but
    built-in defaults must be indistinguishable from PlatformSettings()'s own
    hardcoded defaults, since nothing calls this yet."""
    loader = ConfigurationLoader(providers=[DefaultConfigurationProvider()])

    loaded = load_platform_settings(loader)

    assert loaded == PlatformSettings()


def test_overriding_via_environment_variables():
    loader = ConfigurationLoader(
        providers=[
            DefaultConfigurationProvider(),
            EnvironmentVariablesProvider(
                environ={"ELEVEL_ENVIRONMENT": "production", "ELEVEL_DEFAULT_TIMEOUT": "45"}
            ),
        ]
    )

    settings = load_platform_settings(loader)

    assert settings.environment == Environment.PRODUCTION
    assert settings.default_timeout == 45.0
    # everything untouched by the environment override keeps its default
    assert settings.application_name == "Elevel Prospect AI"


def test_an_invalid_merged_configuration_raises_before_producing_settings():
    loader = ConfigurationLoader(providers=[DefaultConfigurationProvider()])

    class _BadOverride:
        def load(self) -> dict:
            return {"environment": "moon"}

    loader.providers.append(_BadOverride())

    with pytest.raises(InvalidConfigurationError):
        load_platform_settings(loader)


def test_a_custom_validator_is_used_when_given():
    calls: list[dict] = []

    class _RecordingValidator:
        def validate(self, raw: dict) -> None:
            calls.append(raw)

    load_platform_settings(
        ConfigurationLoader(providers=[DefaultConfigurationProvider()]),
        validator=_RecordingValidator(),
    )

    assert len(calls) == 1
