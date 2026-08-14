class ConfigurationError(Exception):
    """Root of every exception raised inside the Configuration System."""


class InvalidConfigurationError(ConfigurationError):
    """Raised by ConfigurationValidator when a raw configuration dict fails
    validation. Carries every problem found, not just the first one."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid configuration: " + "; ".join(errors))
