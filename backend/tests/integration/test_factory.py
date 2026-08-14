from app.integration.adapters.crm_adapter import CRMAdapter
from app.integration.adapters.decision_adapter import DecisionAdapter
from app.integration.adapters.observability_adapter import ObservabilityAdapter
from app.integration.adapters.rules_adapter import RulesAdapter
from app.integration.integration_factory import build_vertical_slice
from app.integration.vertical_slice import VerticalSlice
from app.runtime.engine.runtime_engine import RuntimeEngine


def test_build_vertical_slice_wires_every_adapter_by_default():
    slice_ = build_vertical_slice()

    assert isinstance(slice_, VerticalSlice)
    assert isinstance(slice_.runtime_engine, RuntimeEngine)
    assert isinstance(slice_.decision_adapter, DecisionAdapter)
    assert isinstance(slice_.rules_adapter, RulesAdapter)
    assert isinstance(slice_.crm_adapter, CRMAdapter)
    assert isinstance(slice_.observability_adapter, ObservabilityAdapter)


def test_build_vertical_slice_always_builds_a_real_runtime_engine():
    """runtime_engine is the only mandatory collaborator — there is no flag
    to disable it, since it's what this vertical slice exists to prove."""
    slice_ = build_vertical_slice(
        enable_decision=False, enable_rules=False, enable_crm=False, enable_observability=False
    )

    assert isinstance(slice_.runtime_engine, RuntimeEngine)


def test_build_vertical_slice_with_every_optional_adapter_disabled():
    slice_ = build_vertical_slice(
        enable_decision=False, enable_rules=False, enable_crm=False, enable_observability=False
    )

    assert slice_.decision_adapter is None
    assert slice_.rules_adapter is None
    assert slice_.crm_adapter is None
    assert slice_.observability_adapter is None


def test_build_vertical_slice_can_disable_a_single_adapter():
    slice_ = build_vertical_slice(enable_crm=False)

    assert slice_.crm_adapter is None
    assert slice_.decision_adapter is not None
    assert slice_.rules_adapter is not None
    assert slice_.observability_adapter is not None
