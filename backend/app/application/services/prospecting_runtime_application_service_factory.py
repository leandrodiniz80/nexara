from app.application.execution.execution_result_processor_factory import (
    build_default_execution_result_processor,
)
from app.application.execution.execution_service_factory import build_default_execution_service
from app.application.services.prospecting_runtime_application_service import (
    ProspectingRuntimeApplicationService,
)
from app.business_rules.engine.rules_engine_factory import build_default_rules_engine
from app.decision.engine.decision_engine_factory import build_default_decision_engine
from app.integration.adapters.decision_adapter import DecisionAdapter
from app.integration.adapters.observability_adapter import ObservabilityAdapter
from app.integration.adapters.rules_adapter import RulesAdapter
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)


def build_default_prospecting_runtime_application_service(
    *,
    enable_decision: bool = True,
    enable_rules: bool = True,
    enable_observability: bool = True,
) -> ProspectingRuntimeApplicationService:
    """Composition root for this service — the *only* place that wires the
    real ExecutionService and ExecutionResultProcessor together with the
    (optional) real Decision/Rules/Observability engines behind their
    existing app.integration adapters.

    Since Sprint 32, this factory no longer wires CRM directly (there is no
    `enable_crm` flag here anymore): CRM availability is entirely
    ExecutionResultProcessor's own factory's concern, itself driven by
    PlatformSettings through Bootstrap. Nothing is constructed by hand.
    """
    return ProspectingRuntimeApplicationService(
        execution_service=build_default_execution_service(),
        execution_result_processor=build_default_execution_result_processor(),
        decision_adapter=(
            DecisionAdapter(build_default_decision_engine()) if enable_decision else None
        ),
        rules_adapter=RulesAdapter(build_default_rules_engine()) if enable_rules else None,
        observability_adapter=(
            ObservabilityAdapter(build_default_observability_engine())
            if enable_observability
            else None
        ),
    )
