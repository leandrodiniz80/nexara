import json

from app.config.defaults import default_configuration
from app.config.environment import EnvironmentVariablesProvider
from app.config.loader import ConfigurationLoader
from app.config.providers import DefaultConfigurationProvider, JSONFileConfigurationProvider


class _FakeProvider:
    def __init__(self, values: dict) -> None:
        self.values = values

    def load(self) -> dict:
        return self.values


def test_loader_with_no_providers_given_uses_default_and_environment():
    loader = ConfigurationLoader()

    assert len(loader.providers) == 2


def test_load_with_a_single_provider_returns_its_values():
    loader = ConfigurationLoader(providers=[_FakeProvider({"debug": True})])

    assert loader.load() == {"debug": True}


def test_load_merges_multiple_providers_in_order():
    loader = ConfigurationLoader(
        providers=[
            _FakeProvider({"debug": False, "environment": "development"}),
            _FakeProvider({"debug": True}),
        ]
    )

    result = loader.load()

    assert result == {"debug": True, "environment": "development"}


def test_later_providers_override_earlier_ones_key_by_key():
    loader = ConfigurationLoader(
        providers=[
            DefaultConfigurationProvider(),
            _FakeProvider({"application_name": "Overridden"}),
        ]
    )

    result = loader.load()

    assert result["application_name"] == "Overridden"
    assert result["default_timeout"] == default_configuration()["default_timeout"]


def test_environment_variables_provider_overrides_the_default_provider():
    loader = ConfigurationLoader(
        providers=[
            DefaultConfigurationProvider(),
            EnvironmentVariablesProvider(environ={"ELEVEL_DEBUG": "true"}),
        ]
    )

    result = loader.load()

    assert result["debug"] is True
    assert result["application_name"] == default_configuration()["application_name"]


def test_json_file_provider_overrides_earlier_sources(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"application_name": "From JSON"}), encoding="utf-8")

    loader = ConfigurationLoader(
        providers=[DefaultConfigurationProvider(), JSONFileConfigurationProvider(config_file)]
    )

    result = loader.load()

    assert result["application_name"] == "From JSON"


def test_json_file_provider_returns_empty_dict_when_the_file_does_not_exist(tmp_path):
    provider = JSONFileConfigurationProvider(tmp_path / "missing.json")

    assert provider.load() == {}
