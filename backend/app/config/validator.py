from typing import Any

from app.config.constants import Environment, ModuleName
from app.config.exceptions import InvalidConfigurationError

REQUIRED_FIELDS: tuple[str, ...] = (
    "environment",
    "debug",
    "application_name",
    "application_version",
    "database_url",
    "api_version",
    "enabled_modules",
    "default_timeout",
    "default_language",
    "default_timezone",
    "default_ai_provider",
    "default_llm",
    "log_level",
    "worker_enabled",
    "scheduler_enabled",
    "observability_enabled",
    "crm_enabled",
    "runtime_enabled",
    "workflow_enabled",
    "automation_enabled",
)

_TYPE_EXPECTATIONS: dict[str, type | tuple[type, ...]] = {
    "debug": bool,
    "application_name": str,
    "application_version": str,
    "database_url": str,
    "api_version": str,
    "enabled_modules": list,
    "default_timeout": (int, float),
    "default_language": str,
    "default_timezone": str,
    "default_ai_provider": str,
    "default_llm": str,
    "worker_enabled": bool,
    "scheduler_enabled": bool,
    "observability_enabled": bool,
    "crm_enabled": bool,
    "runtime_enabled": bool,
    "workflow_enabled": bool,
    "automation_enabled": bool,
}


class ConfigurationValidator:
    """Validates a raw configuration dict before it becomes a PlatformSettings
    — required fields present, correct types, no negative timeout, a known
    environment, only known module names, and a well-formed semantic version.
    Raises InvalidConfigurationError listing every problem found, rather than
    stopping at the first one.
    """

    def validate(self, raw: dict[str, Any]) -> None:
        errors: list[str] = []
        errors.extend(self._check_required_fields(raw))
        errors.extend(self._check_types(raw))
        errors.extend(self._check_timeout(raw))
        errors.extend(self._check_environment(raw))
        errors.extend(self._check_enabled_modules(raw))
        errors.extend(self._check_version(raw))

        if errors:
            raise InvalidConfigurationError(errors)

    @staticmethod
    def _check_required_fields(raw: dict[str, Any]) -> list[str]:
        return [
            f"Missing required field '{field}'." for field in REQUIRED_FIELDS if field not in raw
        ]

    @staticmethod
    def _check_types(raw: dict[str, Any]) -> list[str]:
        errors = []
        for field, expected_type in _TYPE_EXPECTATIONS.items():
            if field in raw and not isinstance(raw[field], expected_type):
                errors.append(
                    f"Field '{field}' must be of type {expected_type}, "
                    f"got {type(raw[field]).__name__}."
                )
        return errors

    @staticmethod
    def _check_timeout(raw: dict[str, Any]) -> list[str]:
        timeout = raw.get("default_timeout")
        if isinstance(timeout, (int, float)) and timeout < 0:
            return ["default_timeout must not be negative."]
        return []

    @staticmethod
    def _check_environment(raw: dict[str, Any]) -> list[str]:
        environment = raw.get("environment")
        if isinstance(environment, str) and environment not in {e.value for e in Environment}:
            return [f"Unknown environment '{environment}'."]
        return []

    @staticmethod
    def _check_enabled_modules(raw: dict[str, Any]) -> list[str]:
        enabled_modules = raw.get("enabled_modules")
        if isinstance(enabled_modules, list):
            known = {m.value for m in ModuleName}
            unknown = sorted({str(m) for m in enabled_modules} - known)
            if unknown:
                return [f"Unknown module(s): {unknown}."]
        return []

    @staticmethod
    def _check_version(raw: dict[str, Any]) -> list[str]:
        version = raw.get("application_version")
        if isinstance(version, str) and not _is_valid_semantic_version(version):
            return [f"Invalid application_version '{version}'."]
        return []


def _is_valid_semantic_version(version: str) -> bool:
    parts = version.split(".")
    return len(parts) == 3 and all(part.isdigit() for part in parts)
