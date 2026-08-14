import pytest

from app.config.defaults import default_configuration
from app.config.exceptions import InvalidConfigurationError
from app.config.validator import ConfigurationValidator


def _valid_config() -> dict:
    return default_configuration()


def test_a_valid_configuration_raises_nothing():
    ConfigurationValidator().validate(_valid_config())


def test_missing_required_fields_are_all_reported():
    with pytest.raises(InvalidConfigurationError) as exc_info:
        ConfigurationValidator().validate({})

    assert len(exc_info.value.errors) == len(_valid_config())


def test_wrong_type_is_reported():
    config = _valid_config()
    config["debug"] = "not-a-bool"

    with pytest.raises(InvalidConfigurationError) as exc_info:
        ConfigurationValidator().validate(config)

    assert any("debug" in error for error in exc_info.value.errors)


def test_negative_timeout_is_reported():
    config = _valid_config()
    config["default_timeout"] = -5

    with pytest.raises(InvalidConfigurationError) as exc_info:
        ConfigurationValidator().validate(config)

    assert any("default_timeout" in error for error in exc_info.value.errors)


def test_zero_timeout_is_accepted():
    config = _valid_config()
    config["default_timeout"] = 0

    ConfigurationValidator().validate(config)


def test_unknown_environment_is_reported():
    config = _valid_config()
    config["environment"] = "moon"

    with pytest.raises(InvalidConfigurationError) as exc_info:
        ConfigurationValidator().validate(config)

    assert any("environment" in error for error in exc_info.value.errors)


def test_unknown_module_is_reported():
    config = _valid_config()
    config["enabled_modules"] = ["crm", "not_a_real_module"]

    with pytest.raises(InvalidConfigurationError) as exc_info:
        ConfigurationValidator().validate(config)

    assert any("not_a_real_module" in error for error in exc_info.value.errors)


@pytest.mark.parametrize("bad_version", ["1.2", "not-a-version", "1.2.x", "1.2.3.4"])
def test_invalid_versions_are_reported(bad_version):
    config = _valid_config()
    config["application_version"] = bad_version

    with pytest.raises(InvalidConfigurationError) as exc_info:
        ConfigurationValidator().validate(config)

    assert any("application_version" in error for error in exc_info.value.errors)


def test_multiple_problems_are_all_reported_at_once():
    config = _valid_config()
    config["default_timeout"] = -1
    config["environment"] = "moon"

    with pytest.raises(InvalidConfigurationError) as exc_info:
        ConfigurationValidator().validate(config)

    assert len(exc_info.value.errors) == 2
