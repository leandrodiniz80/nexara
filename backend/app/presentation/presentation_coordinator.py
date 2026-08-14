from collections.abc import Sequence

from app.presentation.executive_payload_service import ExecutivePayloadService
from app.presentation.executive_view_service import ExecutiveViewService
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_result import PresentationResult
from app.presentation.response_envelope_service import ResponseEnvelopeService


class PresentationCoordinator:
    """Coordinates the Presentation layer's full composition chain —
    ExecutiveViewService, then ExecutivePayloadService, then
    ResponseEnvelopeService — producing one PresentationResult. It never
    instantiates a domain or Presentation object directly, never
    recalculates anything, never duplicates any of those services' own
    logic: every step is a plain delegation to the service already
    responsible for it. It knows nothing beyond the Presentation layer —
    no CRM, no Runtime, no Workflow, no Application.
    """

    def __init__(
        self,
        executive_view_service: ExecutiveViewService,
        executive_payload_service: ExecutivePayloadService,
        response_envelope_service: ResponseEnvelopeService,
    ) -> None:
        self._executive_view_service = executive_view_service
        self._executive_payload_service = executive_payload_service
        self._response_envelope_service = response_envelope_service

    def present(
        self,
        dashboard: DashboardView,
        report: ReportView,
        kpis: list[KPIView],
        *,
        warnings: Sequence[str] = (),
        request_id: str | None = None,
    ) -> PresentationResult:
        view = self._executive_view_service.compose(dashboard, report, kpis)
        payload = self._executive_payload_service.build(view)
        response = self._response_envelope_service.success(
            payload, warnings=warnings, request_id=request_id
        )
        return PresentationResult(view=view, payload=payload, response=response)
