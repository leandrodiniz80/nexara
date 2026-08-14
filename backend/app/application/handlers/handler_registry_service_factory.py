from app.application.handlers.executive_dashboard_handler import ExecutiveDashboardHandler
from app.application.handlers.handler_registry_service import HandlerRegistryService
from app.application.public.public_use_case_service_factory import (
    build_default_public_use_case_service,
)


def build_default_handler_registry_service() -> HandlerRegistryService:
    """Composition root for this service. Registers the platform's first
    concrete CommandHandler — ExecutiveDashboardHandler, wired exclusively
    through `build_default_public_use_case_service()` — and nothing else.
    """
    executive_dashboard_handler = ExecutiveDashboardHandler(
        build_default_public_use_case_service()
    )
    return HandlerRegistryService((executive_dashboard_handler,))
