import os
from typing import Any


class EnvironmentVariablesProvider:
    """Reads real OS environment variables prefixed with `prefix` (default
    "ELEVEL_"), lower-casing the remainder to match PlatformSettings' field
    names — e.g. ELEVEL_DEBUG=true -> {"debug": True}. "true"/"false" become
    booleans, a comma-separated value becomes a list (used for
    `enabled_modules`), and a numeric-looking value becomes an int or float;
    everything else stays a string.

    `environ` defaults to the real `os.environ` but accepts an injected dict
    for tests, so reading real environment variables never leaks between
    test runs.
    """

    def __init__(self, *, prefix: str = "ELEVEL_", environ: dict[str, str] | None = None) -> None:
        self.prefix = prefix
        self._environ = environ if environ is not None else os.environ

    def load(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, raw_value in self._environ.items():
            if not key.startswith(self.prefix):
                continue
            field_name = key[len(self.prefix) :].lower()
            values[field_name] = self._coerce(raw_value)
        return values

    @staticmethod
    def _coerce(raw_value: str) -> Any:
        lowered = raw_value.strip().lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        if "," in raw_value:
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        try:
            return int(raw_value)
        except ValueError:
            pass
        try:
            return float(raw_value)
        except ValueError:
            pass
        return raw_value
