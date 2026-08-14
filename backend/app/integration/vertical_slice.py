import time
import uuid
from typing import Any

from app.application.services.application_service_result import ApplicationServiceResult
from app.application.tasks.context.task_context import TaskContext
from app.integration.adapters.crm_adapter import CRMAdapter
from app.integration.adapters.decision_adapter import DecisionAdapter
from app.integration.adapters.observability_adapter import ObservabilityAdapter
from app.integration.adapters.rules_adapter import RulesAdapter
from app.runtime.engine.runtime_engine import RuntimeEngine
from app.runtime.models.execution_context import ExecutionContext
from app.workflows.schemas.workflow_request import WorkflowRequest

DEFAULT_WORKFLOW_NAME = "Prospecting Workflow"


class VerticalSlice:
    """Demonstrates one full prospecting execution across the platform's real
    architecture — an optional Business Rules eligibility check, an optional
    Decision consultation for which Workflow to run, RuntimeEngine.execute_workflow()
    (which drives WorkflowEngine -> TaskExecutor -> the real ResearchTask/
    QualificationTask/CopyTask chain, exactly as it already worked before this
    sprint), an optional CRM opportunity registration, and an optional
    Observability record — reported as a single ApplicationServiceResult.

    It implements no new business rule and constructs no new Engine: every
    collaborator here is injected, and `runtime_engine` is the only mandatory
    one. `decision_adapter`/`rules_adapter`/`crm_adapter`/`observability_adapter`
    are all optional — passing None for any of them skips that step entirely,
    and if a given one raises, that failure is downgraded to a warning and the
    rest of the pipeline still runs, since none of those four steps are what
    this class exists to prove works end to end (the Runtime/Workflow/
    TaskExecutor path is). A failure actually running the Workflow itself,
    however, does mark the whole result unsuccessful — there is no prospecting
    outcome to report otherwise.
    """

    def __init__(
        self,
        runtime_engine: RuntimeEngine,
        *,
        decision_adapter: DecisionAdapter | None = None,
        rules_adapter: RulesAdapter | None = None,
        crm_adapter: CRMAdapter | None = None,
        observability_adapter: ObservabilityAdapter | None = None,
        default_workflow_name: str = DEFAULT_WORKFLOW_NAME,
    ) -> None:
        self.runtime_engine = runtime_engine
        self.decision_adapter = decision_adapter
        self.rules_adapter = rules_adapter
        self.crm_adapter = crm_adapter
        self.observability_adapter = observability_adapter
        self.default_workflow_name = default_workflow_name

    async def run_prospecting(
        self,
        *,
        company_name: str,
        mission_id: uuid.UUID | None = None,
        variables: dict[str, Any] | None = None,
    ) -> ApplicationServiceResult:
        start = time.perf_counter()
        variables = dict(variables or {})
        warnings: list[str] = []
        errors: list[str] = []

        if self.rules_adapter is not None:
            try:
                if not self.rules_adapter.is_eligible(variables):
                    errors.append("Business Rules determined this mission is not eligible.")
                    return self._result(False, None, warnings, errors, start)
            except Exception as exc:
                warnings.append(f"RulesAdapter failed, proceeding without it: {exc}")

        workflow_name = self.default_workflow_name
        if self.decision_adapter is not None:
            try:
                chosen = self.decision_adapter.choose_workflow(variables)
                if chosen is not None:
                    workflow_name = chosen
            except Exception as exc:
                warnings.append(f"DecisionAdapter failed, using default workflow: {exc}")

        execution_context = ExecutionContext(
            mission_id=mission_id,
            workflow_request=WorkflowRequest(
                workflow_name=workflow_name,
                context=TaskContext(mission_id=mission_id, variables=variables),
            ),
        )

        try:
            execution_result = await self.runtime_engine.execute_workflow(execution_context)
        except Exception as exc:
            errors.append(f"Runtime execution failed: {exc}")
            return self._result(False, None, warnings, errors, start)

        warnings.extend(execution_result.warnings)
        errors.extend(execution_result.errors)

        opportunity = None
        if self.crm_adapter is not None:
            try:
                opportunity = self.crm_adapter.create_opportunity(
                    company_name=company_name,
                    opportunity_title=f"Prospecting - {company_name}",
                )
            except Exception as exc:
                warnings.append(f"CRMAdapter failed, continuing without CRM registration: {exc}")

        if self.observability_adapter is not None:
            try:
                self.observability_adapter.record(
                    operation="run_prospecting",
                    execution_time=time.perf_counter() - start,
                    success=execution_result.success,
                )
            except Exception as exc:
                warnings.append(f"ObservabilityAdapter failed: {exc}")

        data = {"execution": execution_result, "opportunity": opportunity}
        return self._result(execution_result.success, data, warnings, errors, start)

    @staticmethod
    def _result(
        success: bool,
        data: Any | None,
        warnings: list[str],
        errors: list[str],
        start: float,
    ) -> ApplicationServiceResult:
        return ApplicationServiceResult(
            success=success,
            data=data,
            warnings=warnings,
            errors=errors,
            execution_time=time.perf_counter() - start,
        )
