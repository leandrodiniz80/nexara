from collections.abc import Sequence
from typing import Any

from app.interface.platform_interface import PlatformInterface


class ApplicationInterfaceService:
    """The Application layer's single public door for external consumers.
    It never instantiates, never transforms, never recalculates, and
    knows nothing about CRM, Runtime, Workflow, Presentation, or
    Contracts — not ResponseMapper, not PresentationFacade. It knows
    exclusively PlatformInterface, and only ever delegates `present()` to
    it, returning exactly the PublicResponse PlatformInterface produces —
    never a ResponseEnvelope.

    Every parameter and return value here is deliberately typed `Any`:
    naming DashboardView/ReportView/KPIView/PublicResponse would require
    importing from Presentation or Contracts, which this service must
    never do.
    """

    def __init__(self, platform_interface: PlatformInterface) -> None:
        self._platform_interface = platform_interface

    def present(
        self,
        dashboard: Any,
        report: Any,
        kpis: list[Any],
        *,
        warnings: Sequence[str] = (),
        request_id: str | None = None,
    ) -> Any:
        return self._platform_interface.present(
            dashboard, report, kpis, warnings=warnings, request_id=request_id
        )
