import time
from typing import Any

from app.application.execution.execution_processing_result import ExecutionProcessingResult
from app.integration.adapters.crm_adapter import CRMAdapter
from app.runtime.models.execution_result import ExecutionResult
from app.schemas.prospecting.company import CompanyRead
from app.schemas.prospecting.prospect import ProspectRead


class ExecutionResultProcessor:
    """Interprets an already-produced ExecutionResult and turns it into
    commercial effects — today, registering a CRM opportunity via the
    existing CRMAdapter (app.integration.adapters.crm_adapter) when a valid
    Company and Prospect are both given. It never executes a Workflow, never
    calls Runtime, never calls a Task: it only receives a finished
    ExecutionResult and reacts to it.

    All processing here is defensive: if CRM is unavailable, or the adapter
    raises for any reason, that failure becomes a warning, never a raised
    exception — the underlying execution's own success is never altered by a
    downstream commercial-effect failure.
    """

    def __init__(self, crm_adapter: CRMAdapter | None = None) -> None:
        self.crm_adapter = crm_adapter

    def process(
        self,
        execution_result: ExecutionResult,
        *,
        company: CompanyRead | None = None,
        prospect: ProspectRead | None = None,
        variables: dict[str, Any] | None = None,
    ) -> ExecutionProcessingResult:
        start = time.perf_counter()
        warnings = list(execution_result.warnings)
        errors = list(execution_result.errors)

        opportunity = None
        if self.crm_adapter is not None and company is not None and prospect is not None:
            company_name = company.trade_name or company.legal_name
            try:
                opportunity = self.crm_adapter.create_opportunity(
                    company_name=company_name,
                    opportunity_title=f"Prospecting - {company_name}",
                )
            except Exception as exc:
                warnings.append(f"CRMAdapter failed, continuing without CRM registration: {exc}")

        return ExecutionProcessingResult(
            execution_result=execution_result,
            crm_opportunity=opportunity,
            warnings=warnings,
            errors=errors,
            execution_time=time.perf_counter() - start,
        )
