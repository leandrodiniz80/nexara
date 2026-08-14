from app.config.loader import ConfigurationLoader
from app.config.settings import PlatformSettings
from app.config.validator import ConfigurationValidator


def load_platform_settings(
    loader: ConfigurationLoader | None = None,
    *,
    validator: ConfigurationValidator | None = None,
) -> PlatformSettings:
    """The single entrypoint for producing a ready, validated PlatformSettings
    — loads raw configuration from the given (or default) ConfigurationLoader,
    validates it, and returns an immutable PlatformSettings.

    Calling this with no arguments at all builds a PlatformSettings from
    nothing but the platform's built-in defaults plus whatever real
    `ELEVEL_*` environment variables happen to be set — never raises,
    never requires any file to exist.

    This is the future entrypoint Bootstrap/API/Runtime/Workers/Scheduler/CLI/
    Frontend will call to get the platform's configuration; nothing outside
    app.config calls it yet — that wiring is a future integration sprint's
    job, not this one's.
    """
    loader = loader or ConfigurationLoader()
    validator = validator or ConfigurationValidator()
    raw = loader.load()
    validator.validate(raw)
    return PlatformSettings.from_dict(raw)
