import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.application.interface.application_interface_service import ApplicationInterfaceService
from app.application.public import public_use_case_service
from app.application.public.public_use_case import PublicUseCase
from app.application.public.public_use_case_service import PublicUseCaseService
from app.application.public.public_use_case_service_factory import (
    build_default_public_use_case_service,
)
from app.contracts.public_response import PublicResponse
from app.contracts.response_mapper import ResponseMapper
from app.crm.services.sales_report_section import SalesReportSection
from app.interface.platform_interface import PlatformInterface
from app.operations.coordinator.operation_context import OperationContext
from app.operations.coordinator.operation_result import OperationResult
from app.presentation.executive_payload_service import ExecutivePayloadService
from app.presentation.executive_view_service import ExecutiveViewService
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_coordinator import PresentationCoordinator
from app.presentation.presentation_facade import PresentationFacade
from app.presentation.response_envelope_service import ResponseEnvelopeService

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _dashboard_view() -> DashboardView:
    return DashboardView(
        title="Sales Dashboard",
        overall_health="good",
        overall_score=60.0,
        cards=[{"label": "Expected Revenue", "value": 5000.0}],
        highlights=["Alta confiança na previsão"],
        warnings=["Meta distante"],
        generated_at=_T0,
    )


def _report_view() -> ReportView:
    return ReportView(
        title="Executive Sales Report",
        subtitle=_T0.isoformat(),
        sections=[SalesReportSection(title="Resumo Executivo", items={"overall_score": 60.0})],
        footer="Generated automatically by Elevel Prospect AI",
    )


def _kpi_views() -> list[KPIView]:
    return [KPIView(name="Forecast Confidence", value=60.0, unit="%", status="ATTENTION")]


def _real_application_interface_service() -> ApplicationInterfaceService:
    coordinator = PresentationCoordinator(
        ExecutiveViewService(), ExecutivePayloadService(), ResponseEnvelopeService()
    )
    facade = PresentationFacade(coordinator)
    platform_interface = PlatformInterface(facade, ResponseMapper())
    return ApplicationInterfaceService(platform_interface)


class _CountingApplicationInterfaceService:
    def __init__(self) -> None:
        self.calls = 0
        self.received_args: tuple | None = None
        self._real = _real_application_interface_service()

    def present(self, dashboard, report, kpis, *, warnings=(), request_id=None):
        self.calls += 1
        self.received_args = (dashboard, report, kpis, warnings, request_id)
        return self._real.present(
            dashboard, report, kpis, warnings=warnings, request_id=request_id
        )


class _FakeOperationsCoordinator:
    def __init__(self, *, success: bool = True, reason: str | None = None) -> None:
        self.success = success
        self.reason = reason
        self.calls: list[OperationContext] = []

    def run(self, context: OperationContext) -> OperationResult:
        self.calls.append(context)
        return OperationResult(success=self.success, reason=self.reason, execution_time=0.0)


def test_execute_forwards_the_exact_arguments():
    application_interface_service = _CountingApplicationInterfaceService()
    service = PublicUseCaseService(application_interface_service, _FakeOperationsCoordinator())
    dashboard, report, kpis = _dashboard_view(), _report_view(), _kpi_views()

    service.execute(dashboard, report, kpis, warnings=["Meta distante"], request_id="req-1")

    assert application_interface_service.received_args == (
        dashboard,
        report,
        kpis,
        ["Meta distante"],
        "req-1",
    )


def test_application_interface_service_chamado_exatamente_uma_vez():
    application_interface_service = _CountingApplicationInterfaceService()
    service = PublicUseCaseService(application_interface_service, _FakeOperationsCoordinator())

    service.execute(_dashboard_view(), _report_view(), _kpi_views())

    assert application_interface_service.calls == 1


def test_operations_coordinator_chamado_exatamente_uma_vez():
    operations_coordinator = _FakeOperationsCoordinator()
    service = PublicUseCaseService(_CountingApplicationInterfaceService(), operations_coordinator)

    service.execute(_dashboard_view(), _report_view(), _kpi_views())

    assert len(operations_coordinator.calls) == 1


def test_falha_operacional_interrompe_o_fluxo():
    operations_coordinator = _FakeOperationsCoordinator(
        success=False, reason="Operations engine is down."
    )
    service = PublicUseCaseService(_CountingApplicationInterfaceService(), operations_coordinator)

    result = service.execute(_dashboard_view(), _report_view(), _kpi_views())

    assert isinstance(result, OperationResult)
    assert result.success is False
    assert result.reason == "Operations engine is down."


def test_application_interface_service_nunca_chamado_quando_ha_falha_operacional():
    application_interface_service = _CountingApplicationInterfaceService()
    operations_coordinator = _FakeOperationsCoordinator(success=False)
    service = PublicUseCaseService(application_interface_service, operations_coordinator)

    service.execute(_dashboard_view(), _report_view(), _kpi_views())

    assert application_interface_service.calls == 0


def test_sucesso_continua_exatamente_igual():
    application_interface_service = _CountingApplicationInterfaceService()
    operations_coordinator = _FakeOperationsCoordinator(success=True)
    service = PublicUseCaseService(application_interface_service, operations_coordinator)
    dashboard, report, kpis = _dashboard_view(), _report_view(), _kpi_views()

    result = service.execute(dashboard, report, kpis, request_id="req-9")

    assert application_interface_service.calls == 1
    assert application_interface_service.received_args == (dashboard, report, kpis, (), "req-9")
    assert isinstance(result, PublicResponse)
    assert result.success is True


def test_retorno_e_public_response():
    service = PublicUseCaseService(
        _real_application_interface_service(), _FakeOperationsCoordinator()
    )

    result = service.execute(_dashboard_view(), _report_view(), _kpi_views())

    assert isinstance(result, PublicResponse)
    assert result.success is True


def test_list_use_cases_returns_exactly_the_executive_dashboard_use_case():
    service = PublicUseCaseService(
        _real_application_interface_service(), _FakeOperationsCoordinator()
    )

    use_cases = service.list_use_cases()

    assert len(use_cases) == 1
    use_case = use_cases[0]
    assert isinstance(use_case, PublicUseCase)
    assert use_case.name == "executive_dashboard"
    assert use_case.description == "Build executive commercial dashboard."
    assert use_case.enabled is True


def test_imutabilidade_rejects_attribute_assignment():
    service = PublicUseCaseService(
        _real_application_interface_service(), _FakeOperationsCoordinator()
    )
    use_case = service.list_use_cases()[0]

    with pytest.raises(ValidationError):
        use_case.enabled = False


def test_injecao_uses_exactly_the_collaborators_provided():
    application_interface_service = _CountingApplicationInterfaceService()
    operations_coordinator = _FakeOperationsCoordinator()

    service = PublicUseCaseService(application_interface_service, operations_coordinator)

    assert service._application_interface_service is application_interface_service
    assert service._operations_coordinator is operations_coordinator


def test_build_default_public_use_case_service_returns_a_usable_service():
    service = build_default_public_use_case_service()

    assert isinstance(service, PublicUseCaseService)
    result = service.execute(_dashboard_view(), _report_view(), _kpi_views())
    assert isinstance(result, PublicResponse)


def test_nenhum_import_de_crm():
    source = inspect.getsource(public_use_case_service)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(public_use_case_service)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(public_use_case_service)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(public_use_case_service)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(public_use_case_service)
    assert "app.contracts" not in source
