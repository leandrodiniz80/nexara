from app.config.constants import ModuleName
from app.config.defaults import default_configuration
from app.config.validator import REQUIRED_FIELDS, ConfigurationValidator


def test_default_configuration_contains_every_required_field():
    config = default_configuration()

    for field in REQUIRED_FIELDS:
        assert field in config


def test_default_configuration_is_itself_valid():
    ConfigurationValidator().validate(default_configuration())


def test_default_configuration_enables_every_known_module():
    config = default_configuration()

    assert set(config["enabled_modules"]) == {module.value for module in ModuleName}


def test_default_configuration_matches_known_defaults():
    config = default_configuration()

    assert config["environment"] == "development"
    assert config["debug"] is False
    assert config["application_name"] == "Elevel Prospect AI"
    assert config["default_timeout"] == 30.0
    assert config["default_language"] == "pt-BR"
    assert config["log_level"] == "info"


def test_default_configuration_is_a_fresh_dict_each_call():
    first = default_configuration()
    second = default_configuration()

    first["debug"] = True

    assert second["debug"] is False
