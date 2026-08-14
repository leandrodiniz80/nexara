import time
import uuid
from typing import Any, ClassVar

from app.application.execution.execution_result_processor import ExecutionResultProcessor
from app.application.execution.execution_service import (
    DEFAULT_PROSPECTING_WORKFLOW_NAME,
    ExecutionService,
)
from app.application.services.application_service_result import ApplicationServiceResult
from app.application.services.base_application_service import BaseApplicationService
from app.integration.adapters.decision_adapter import DecisionAdapter
from app.integration.adapters.observability_adapter import ObservabilityAdapter
from app.integration.adapters.rules_adapter import RulesAdapter

DEFAULT_WORKFLOW_NAME = DEFAULT_PROSPECTING_WORKFLOW_NAME


class ProspectingRuntimeApplicationService(BaseApplicationService):
    """The platform's first official Runtime consumer — a new, independent
    Application Service that runs a prospecting execution entirely through
    ExecutionService.execute_prospecting() (which itself delegates to
    RuntimeEngine.execute_workflow() -> WorkflowEngine -> TaskExecutor ->
    ResearchTask -> QualificationTask -> CopyTask, none of it touched by this
    sprint), with an optional Business Rules eligibility check and an
    optional Decision consultation for which Workflow to run.

    Since Sprint 32, this service no longer knows CRM exists at all — every
    commercial effect (creating a CRM opportunity) is decided entirely by
    ExecutionResultProcessor, injected here as its own collaborator, and
    reached only by handing it the already-finished ExecutionResult plus
    whatever `company`/`prospect` the caller's own `variables` happen to
    carry. This service only decides *whether* to run (Business Rules) and
    *which* Workflow to run (Decision) — everything after Runtime finishes
    belongs to ExecutionResultProcessor.

    It coexists with MissionApplicationService, which is completely
    untouched and keeps using its own CreateProspectingMissionUseCase-based
    path exactly as before — this class does not replace, wrap, or call it.
    """

    service_name: ClassVar[str] = "prospecting_runtime_application_service"

    def __init__(
        self,
        execution_service: ExecutionService,
        execution_result_processor: ExecutionResultProcessor,
        *,
        decision_adapter: DecisionAdapter | None = None,
        rules_adapter: RulesAdapter | None = None,
        observability_adapter: ObservabilityAdapter | None = None,
        default_workflow_name: str = DEFAULT_WORKFLOW_NAME,
    ) -> None:
        super().__init__()
        self.execution_service = execution_service
        self.execution_result_processor = execution_result_processor
        self.decision_adapter = decision_adapter
        self.rules_adapter = rules_adapter
        self.observability_adapter = observability_adapter
        self.default_workflow_name = default_workflow_name

    async def run_prospecting(
        self,
        *,
        mission_id: uuid.UUID | None = None,
        variables: dict[str, Any] | None = None,
    ) -> ApplicationServiceResult:
        async def _operation():
            start = time.perf_counter()
            resolved_variables = dict(variables or {})
            warnings: list[str] = []

            if self.rules_adapter is not None:
                try:
                    eligible = self.rules_adapter.is_eligible(resolved_variables)
                except Exception as exc:
                    warnings.append(f"RulesAdapter failed, proceeding without it: {exc}")
                    eligible = True
                if not eligible:
                    raise ValueError("Business Rules determined this mission is not eligible.")

            workflow_name = self.default_workflow_name
            if self.decision_adapter is not None:
                try:
                    chosen = self.decision_adapter.choose_workflow(resolved_variables)
                    if chosen is not None:
                        workflow_name = chosen
                except Exception as exc:
                    warnings.append(f"DecisionAdapter failed, using default workflow: {exc}")

            execution_result = await self.execution_service.execute_prospecting(
                workflow_name=workflow_name, mission_id=mission_id, variables=resolved_variables
            )

            processing_result = self.execution_result_processor.process(
                execution_result,
                company=resolved_variables.get("company"),
                prospect=resolved_variables.get("prospect"),
                variables=resolved_variables,
            )
            processing_result.warnings = warnings + processing_result.warnings

            if self.observability_adapter is not None:
                try:
                    self.observability_adapter.record(
                        operation="run_prospecting",
                        execution_time=time.perf_counter() - start,
                        success=execution_result.success,
                    )
                except Exception as exc:
                    processing_result.warnings.append(f"ObservabilityAdapter failed: {exc}")

            return processing_result

        return await self._run("run_prospecting", _operation)
