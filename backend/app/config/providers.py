import json
from pathlib import Path
from typing import Any, Protocol

from app.config.defaults import default_configuration


class ConfigurationProvider(Protocol):
    """Structural contract every configuration source satisfies — a single
    `load() -> dict[str, Any]` returning whatever keys/values it knows about.
    ConfigurationLoader merges these in priority order; a provider with
    nothing to say about a given key simply omits it from its dict.
    """

    def load(self) -> dict[str, Any]: ...


class DefaultConfigurationProvider:
    """The lowest-priority source — the platform's built-in defaults."""

    def load(self) -> dict[str, Any]:
        return default_configuration()


class JSONFileConfigurationProvider:
    """Reads a JSON file of configuration overrides. Real, working file I/O —
    `json` is stdlib, so this provider has no optional dependency. Returns an
    empty dict if the file doesn't exist, the same "nothing to say about any
    key" contract every other provider follows.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        with self.path.open(encoding="utf-8") as file:
            return json.load(file)


class YAMLFileConfigurationProvider:
    """Reads a YAML file of configuration overrides. This sprint builds the
    infrastructure only: `PyYAML` is imported lazily, inside load(), so merely
    importing this module never requires the optional dependency to be
    installed — only actually loading a YAML file does.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        import yaml  # lazy: keeps PyYAML an optional dependency

        with self.path.open(encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
