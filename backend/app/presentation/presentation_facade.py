from collections.abc import Sequence

from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_coordinator import PresentationCoordinator
from app.presentation.response_envelope import ResponseEnvelope


class PresentationFacade:
    """The single public door into the Presentation layer. No future
    consumer is meant to know ExecutiveViewService, ExecutivePayloadService,
    ResponseEnvelopeService or PresentationCoordinator — only this facade.

    It never creates, instantiates, transforms, recalculates, or duplicates
    any logic: it only delegates to the injected PresentationCoordinator
    and hands back exclusively its ResponseEnvelope.
    PresentationResult — an internal detail of this layer's own
    composition chain — never crosses this boundary.
    """

    def __init__(self, coordinator: PresentationCoordinator) -> None:
        self._coordinator = coordinator

    def present(
        self,
        dashboard: DashboardView,
        report: ReportView,
        kpis: list[KPIView],
        *,
        warnings: Sequence[str] = (),
        request_id: str | None = None,
    ) -> ResponseEnvelope:
        result = self._coordinator.present(
            dashboard, report, kpis, warnings=warnings, request_id=request_id
        )
        return result.response
