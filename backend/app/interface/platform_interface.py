from collections.abc import Sequence

from app.contracts.public_response import PublicResponse
from app.contracts.response_mapper import ResponseMapper
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_facade import PresentationFacade


class PlatformInterface:
    """The platform's single public door for any external consumer (REST
    API, GraphQL, CLI, Workers, Scheduler, WebSocket, SDKs). It never
    instantiates, never transforms, never recalculates, and knows nothing
    about the domain — no CRM, no Runtime, no Workflow, no Application. It
    only ever delegates: PresentationFacade.present() produces a
    ResponseEnvelope, which is handed opaquely to
    ResponseMapper.to_public_response() to produce the PublicResponse this
    method always returns — never a ResponseEnvelope.

    This does not reopen the exception granted to ResponseMapper in an
    earlier sprint (the only file allowed to know both ResponseEnvelope
    and PublicResponse at once). PlatformInterface never imports or
    inspects ResponseEnvelope itself — it holds a PresentationFacade
    (which happens to produce one internally) and a ResponseMapper (which
    happens to consume one) as two opaque collaborators, and simply passes
    the value one produces into the other without ever knowing its shape.
    """

    def __init__(
        self,
        presentation_facade: PresentationFacade,
        response_mapper: ResponseMapper,
    ) -> None:
        self._presentation_facade = presentation_facade
        self._response_mapper = response_mapper

    def present(
        self,
        dashboard: DashboardView,
        report: ReportView,
        kpis: list[KPIView],
        *,
        warnings: Sequence[str] = (),
        request_id: str | None = None,
    ) -> PublicResponse:
        envelope = self._presentation_facade.present(
            dashboard, report, kpis, warnings=warnings, request_id=request_id
        )
        return self._response_mapper.to_public_response(envelope)
