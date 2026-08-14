import pytest

from app.bootstrap.configuration import BootstrapConfiguration, InvalidBootstrapConfigurationError
from app.bootstrap.module_loader import BootstrapModule


def test_default_configuration_has_sensible_defaults():
    config = BootstrapConfiguration()

    assert config.environment == "development"
    assert config.application_version == "0.1.0"
    assert config.enabled_modules is None


def test_a_known_environment_is_accepted():
    config = BootstrapConfiguration(environment="production")

    assert config.environment == "production"


def test_an_unknown_environment_raises():
    with pytest.raises(InvalidBootstrapConfigurationError):
        BootstrapConfiguration(environment="not-a-real-environment")


def test_enabled_modules_accepts_bootstrap_module_members():
    config = BootstrapConfiguration(enabled_modules=[BootstrapModule.CRM, BootstrapModule.RUNTIME])

    assert config.enabled_modules == [BootstrapModule.CRM, BootstrapModule.RUNTIME]


def test_enabled_modules_accepts_plain_strings_and_normalizes_them():
    config = BootstrapConfiguration(enabled_modules=["crm", "runtime"])

    assert config.enabled_modules == [BootstrapModule.CRM, BootstrapModule.RUNTIME]


def test_enabled_modules_with_an_unknown_name_raises():
    with pytest.raises(InvalidBootstrapConfigurationError):
        BootstrapConfiguration(enabled_modules=["not-a-real-module"])


def test_application_version_is_stored_as_given():
    config = BootstrapConfiguration(application_version="2.4.0")

    assert config.application_version == "2.4.0"
