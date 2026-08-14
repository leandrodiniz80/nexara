from app.config.environment import EnvironmentVariablesProvider


def test_load_ignores_variables_without_the_prefix():
    provider = EnvironmentVariablesProvider(environ={"PATH": "/usr/bin", "HOME": "/root"})

    assert provider.load() == {}


def test_load_strips_the_prefix_and_lowercases_the_field_name():
    provider = EnvironmentVariablesProvider(environ={"ELEVEL_APPLICATION_NAME": "Custom Name"})

    assert provider.load() == {"application_name": "Custom Name"}


def test_load_coerces_boolean_looking_values():
    provider = EnvironmentVariablesProvider(
        environ={"ELEVEL_DEBUG": "true", "ELEVEL_WORKER_ENABLED": "False"}
    )

    values = provider.load()

    assert values["debug"] is True
    assert values["worker_enabled"] is False


def test_load_coerces_integer_and_float_looking_values():
    provider = EnvironmentVariablesProvider(
        environ={"ELEVEL_DEFAULT_TIMEOUT": "45", "ELEVEL_RETRY_FACTOR": "1.5"}
    )

    values = provider.load()

    assert values["default_timeout"] == 45
    assert isinstance(values["default_timeout"], int)
    assert values["retry_factor"] == 1.5


def test_load_splits_comma_separated_values_into_a_list():
    provider = EnvironmentVariablesProvider(
        environ={"ELEVEL_ENABLED_MODULES": "crm, runtime,decision"}
    )

    values = provider.load()

    assert values["enabled_modules"] == ["crm", "runtime", "decision"]


def test_load_leaves_plain_strings_as_strings():
    provider = EnvironmentVariablesProvider(environ={"ELEVEL_DEFAULT_LANGUAGE": "en-US"})

    assert provider.load() == {"default_language": "en-US"}


def test_a_custom_prefix_is_respected():
    provider = EnvironmentVariablesProvider(
        prefix="MYAPP_", environ={"MYAPP_DEBUG": "true", "ELEVEL_DEBUG": "false"}
    )

    assert provider.load() == {"debug": True}
