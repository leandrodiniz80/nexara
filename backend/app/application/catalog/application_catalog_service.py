from app.application.catalog.application_catalog import ApplicationCatalog
from app.application.catalog.application_operation import ApplicationOperation
from app.application.public.public_use_case import PublicUseCase
from app.application.public.public_use_case_service import PublicUseCaseService

_CATEGORY = "executive"


class ApplicationCatalogService:
    """The platform's official catalog of public operations — pure
    discovery, nothing else: it never executes a use case, never
    integrates with anything, never knows the internal domain. It knows
    exclusively PublicUseCaseService — not CRM, not Runtime, not
    Workflow, not Presentation, not Contracts, not PlatformInterface, not
    ApplicationInterfaceService.

    `build_catalog()` never assembles its list by hand: every
    ApplicationOperation comes from converting one PublicUseCase already
    returned by PublicUseCaseService.list_use_cases().
    """

    def __init__(self, public_use_case_service: PublicUseCaseService) -> None:
        self._public_use_case_service = public_use_case_service

    def build_catalog(self) -> ApplicationCatalog:
        operations = tuple(
            self._to_operation(use_case)
            for use_case in self._public_use_case_service.list_use_cases()
        )
        return ApplicationCatalog(operations=operations)

    def find(self, name: str) -> ApplicationOperation | None:
        for operation in self.build_catalog().operations:
            if operation.name == name:
                return operation
        return None

    @staticmethod
    def _to_operation(use_case: PublicUseCase) -> ApplicationOperation:
        return ApplicationOperation(
            name=use_case.name,
            display_name=use_case.description,
            description=use_case.description,
            category=_CATEGORY,
            enabled=use_case.enabled,
        )
