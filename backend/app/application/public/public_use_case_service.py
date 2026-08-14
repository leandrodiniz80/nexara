from collections.abc import Sequence
from typing import Any

from app.application.interface.application_interface_service import ApplicationInterfaceService
from app.application.public.public_use_case import PublicUseCase
from app.operations.coordinator.operation_context import OperationContext
from app.operations.coordinator.operations_coordinator import OperationsCoordinator

_EXECUTIVE_DASHBOARD_USE_CASE = PublicUseCase(
    name="executive_dashboard",
    description="Build executive commercial dashboard.",
    enabled=True,
)

_OPERATION_NAME = "public_use_case_execute"


class PublicUseCaseService:
    """The platform's first public use-case layer. It never knows CRM,
    Runtime, Workflow, Presentation, Contracts, or PlatformInterface — it
    knows exclusively OperationsCoordinator and ApplicationInterfaceService.

    Every PublicUseCase now passes through OperationsCoordinator before
    executing: `execute()` first calls OperationsCoordinator.run(). When
    that reports an operational failure, `execute()` returns that same
    OperationResult (already shaped with `success=False`) without ever
    calling ApplicationInterfaceService. On operational success, it
    delegates entirely to ApplicationInterfaceService.present(), exactly
    as before. `list_use_cases()` describes what is available to invoke,
    without invoking anything.

    Every parameter and return value on `execute()` is deliberately typed
    `Any`: naming any Presentation/Contracts type would require importing
    from those layers, which this service must never do.

    OperationsCoordinator still knows nothing about Application — this
    dependency is strictly one-directional, the same shape Runtime already
    established with Operations.
    """

    def __init__(
        self,
        application_interface_service: ApplicationInterfaceService,
        operations_coordinator: OperationsCoordinator,
    ) -> None:
        self._application_interface_service = application_interface_service
        self._operations_coordinator = operations_coordinator

    def execute(
        self,
        dashboard: Any,
        report: Any,
        kpis: list[Any],
        *,
        warnings: Sequence[str] = (),
        request_id: str | None = None,
    ) -> Any:
        operation_result = self._operations_coordinator.run(
            OperationContext(operation_name=_OPERATION_NAME)
        )
        if not operation_result.success:
            return operation_result

        return self._application_interface_service.present(
            dashboard, report, kpis, warnings=warnings, request_id=request_id
        )

    def list_use_cases(self) -> list[PublicUseCase]:
        return [_EXECUTIVE_DASHBOARD_USE_CASE]
