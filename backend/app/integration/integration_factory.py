from app.business_rules.engine.rules_engine_factory import build_default_rules_engine
from app.crm.services.crm_engine_factory import build_default_crm_engine
from app.decision.engine.decision_engine_factory import build_default_decision_engine
from app.integration.adapters.crm_adapter import CRMAdapter
from app.integration.adapters.decision_adapter import DecisionAdapter
from app.integration.adapters.observability_adapter import ObservabilityAdapter
from app.integration.adapters.rules_adapter import RulesAdapter
from app.integration.vertical_slice import VerticalSlice
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)
from app.runtime.services.runtime_engine_factory import build_default_runtime_engine


def build_vertical_slice(
    *,
    enable_decision: bool = True,
    enable_rules: bool = True,
    enable_crm: bool = True,
    enable_observability: bool = True,
) -> VerticalSlice:
    """Composition root for this module — the *only* place that wires the
    real RuntimeEngine together with the (optional) real Decision/Rules/CRM/
    Observability engines behind their respective adapters. Every function
    called here is an existing `build_default_*` Factory; nothing is
    constructed by hand, and no Engine anywhere is modified.

    Each `enable_*` flag defaults to True (fully wired) but, when False, the
    matching adapter is simply never constructed — VerticalSlice already
    treats a None adapter as "skip this step", so turning a step off here
    requires no change to VerticalSlice itself.
    """
    return VerticalSlice(
        runtime_engine=build_default_runtime_engine(),
        decision_adapter=(
            DecisionAdapter(build_default_decision_engine()) if enable_decision else None
        ),
        rules_adapter=RulesAdapter(build_default_rules_engine()) if enable_rules else None,
        crm_adapter=CRMAdapter(build_default_crm_engine()) if enable_crm else None,
        observability_adapter=(
            ObservabilityAdapter(build_default_observability_engine())
            if enable_observability
            else None
        ),
    )
