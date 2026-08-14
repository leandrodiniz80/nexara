from typing import Any

from app.config.environment import EnvironmentVariablesProvider
from app.config.providers import ConfigurationProvider, DefaultConfigurationProvider


class ConfigurationLoader:
    """Merges configuration from an ordered list of ConfigurationProviders —
    later providers override earlier ones, key by key. The default order is
    DefaultConfiguration -> EnvironmentVariables; a caller who wants JSON/YAML
    file overrides too supplies their own ordered `providers` list, appending
    a JSONFileConfigurationProvider/YAMLFileConfigurationProvider after the
    defaults.
    """

    def __init__(self, providers: list[ConfigurationProvider] | None = None) -> None:
        self.providers = (
            providers
            if providers is not None
            else [DefaultConfigurationProvider(), EnvironmentVariablesProvider()]
        )

    def load(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for provider in self.providers:
            merged.update(provider.load())
        return merged
