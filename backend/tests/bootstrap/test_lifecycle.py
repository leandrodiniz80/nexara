from app.bootstrap import lifecycle
from app.config.settings import PlatformSettings
from app.crm.engine.crm_engine import CRMEngine

_CRM_ONLY = PlatformSettings(enabled_modules=["crm"])


def setup_function() -> None:
    """Each test starts from a clean slate — lifecycle.py holds process-level
    global state, so a prior test's initialize() must never leak into the
    next one regardless of execution order."""
    lifecycle.shutdown()


def teardown_function() -> None:
    lifecycle.shutdown()


def test_initialize_returns_a_service_locator_with_the_configured_modules():
    locator = lifecycle.initialize(_CRM_ONLY)

    assert locator.has(CRMEngine) is True
    assert isinstance(locator.get(CRMEngine), CRMEngine)


def test_shutdown_after_initialize_clears_the_active_bootstrap():
    lifecycle.initialize(_CRM_ONLY)

    lifecycle.shutdown()

    assert lifecycle._active_bootstrap is None


def test_shutdown_with_nothing_initialized_does_not_raise():
    lifecycle.shutdown()

    assert lifecycle._active_bootstrap is None


def test_initialize_again_after_shutdown_rebuilds_a_fresh_locator():
    first_locator = lifecycle.initialize(_CRM_ONLY)
    first_instance = first_locator.get(CRMEngine)

    lifecycle.shutdown()
    second_locator = lifecycle.initialize(_CRM_ONLY)

    assert second_locator is not first_locator
    assert second_locator.get(CRMEngine) is not first_instance


def test_initialize_with_no_settings_uses_platform_settings_defaults():
    """Backward compatibility: initialize() with nothing given must still
    build every module, exactly as before Bootstrap depended on
    PlatformSettings."""
    locator = lifecycle.initialize()

    assert locator.has(CRMEngine) is True
