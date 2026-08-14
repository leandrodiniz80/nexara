from app.bootstrap.module_loader import BootstrapModule


class InvalidBootstrapConfigurationError(Exception):
    """Raised when a BootstrapConfiguration is constructed with an unknown
    environment or an unknown module name in `enabled_modules`."""


class BootstrapConfiguration:
    """Controls what Bootstrap.initialize() builds: which environment it's
    running in, and which modules to construct. `enabled_modules=None` means
    "build every known module"; an explicit subset restricts it to just those.
    Validated eagerly at construction time — an invalid configuration never
    reaches Bootstrap at all.
    """

    _ALLOWED_ENVIRONMENTS = frozenset({"development", "staging", "production", "test"})

    def __init__(
        self,
        *,
        environment: str = "development",
        application_version: str = "0.1.0",
        enabled_modules: list[BootstrapModule | str] | None = None,
    ) -> None:
        if environment not in self._ALLOWED_ENVIRONMENTS:
            raise InvalidBootstrapConfigurationError(
                f"Unknown environment '{environment}'. Expected one of "
                f"{sorted(self._ALLOWED_ENVIRONMENTS)}."
            )

        self.environment = environment
        self.application_version = application_version
        self.enabled_modules = self._normalize_modules(enabled_modules)

    @staticmethod
    def _normalize_modules(
        enabled_modules: list[BootstrapModule | str] | None,
    ) -> list[BootstrapModule] | None:
        if enabled_modules is None:
            return None
        normalized: list[BootstrapModule] = []
        for module in enabled_modules:
            try:
                normalized.append(BootstrapModule(module))
            except ValueError as exc:
                raise InvalidBootstrapConfigurationError(
                    f"Unknown module '{module}'. Expected one of "
                    f"{[m.value for m in BootstrapModule]}."
                ) from exc
        return normalized
