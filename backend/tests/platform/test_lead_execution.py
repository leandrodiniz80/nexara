"""Tests for LeadExecutionTracker (Sprint 285)."""

import pytest

from app.platform.auth.platform_auth import PlatformAuth
from app.platform.revenue.lead_execution import LeadExecutionTracker


def _tracker_with_org() -> tuple[LeadExecutionTracker, PlatformAuth, str]:
    auth = PlatformAuth()
    org_id = auth.create_organization("Acme")
    return LeadExecutionTracker(auth), auth, org_id


# --- record_action() -------------------------------------------------------


def test_execute_marca_como_contacted():
    tracker, _, org_id = _tracker_with_org()

    result = tracker.record_action(org_id, "upgrade_offer", "execute")

    assert result == {
        "org_id": org_id,
        "lead_type": "upgrade_offer",
        "previous_state": "pending",
        "new_state": "contacted",
    }


def test_ignore_marca_como_ignored():
    tracker, _, org_id = _tracker_with_org()

    result = tracker.record_action(org_id, "retention_offer", "ignore")

    assert result["new_state"] == "ignored"


def test_convert_marca_como_converted():
    tracker, _, org_id = _tracker_with_org()

    result = tracker.record_action(org_id, "expansion_offer", "convert")

    assert result["new_state"] == "converted"


def test_record_action_persiste_via_auth():
    tracker, auth, org_id = _tracker_with_org()

    tracker.record_action(org_id, "upgrade_offer", "execute")

    assert auth.get_lead_state(org_id, "upgrade_offer") == "contacted"


def test_record_action_retorna_estado_anterior_correto():
    tracker, _, org_id = _tracker_with_org()
    tracker.record_action(org_id, "upgrade_offer", "execute")

    result = tracker.record_action(org_id, "upgrade_offer", "convert")

    assert result["previous_state"] == "contacted"
    assert result["new_state"] == "converted"


def test_record_action_lead_type_invalido_levanta_value_error():
    tracker, _, org_id = _tracker_with_org()

    with pytest.raises(ValueError):
        tracker.record_action(org_id, "not-a-real-lead-type", "execute")


def test_record_action_action_invalida_levanta_value_error():
    tracker, _, org_id = _tracker_with_org()

    with pytest.raises(ValueError):
        tracker.record_action(org_id, "upgrade_offer", "not-a-real-action")


def test_record_action_organizacao_inexistente_levanta_lookup_error():
    tracker, _, _ = _tracker_with_org()

    with pytest.raises(LookupError):
        tracker.record_action("does-not-exist", "upgrade_offer", "execute")


def test_record_action_nao_exige_lead_atual_no_playbook():
    """A rep can mark something contacted/converted even after the org
    naturally drops out of a live playbook's candidate list -- this
    tracker has no concept of "current playbook membership" at all,
    deliberately."""
    tracker, _, org_id = _tracker_with_org()

    result = tracker.record_action(org_id, "expansion_offer", "convert")

    assert result["new_state"] == "converted"


def test_lead_types_independentes_para_a_mesma_org():
    tracker, _, org_id = _tracker_with_org()

    tracker.record_action(org_id, "upgrade_offer", "execute")
    tracker.record_action(org_id, "retention_offer", "convert")

    assert tracker.get_state(org_id, "upgrade_offer") == "contacted"
    assert tracker.get_state(org_id, "retention_offer") == "converted"
    assert tracker.get_state(org_id, "expansion_offer") == "pending"


# --- get_state() -------------------------------------------------------


def test_get_state_padrao_e_pending():
    tracker, _, org_id = _tracker_with_org()

    assert tracker.get_state(org_id, "upgrade_offer") == "pending"


# --- conversion_summary() -------------------------------------------------


def test_conversion_summary_retorna_os_tres_lead_types():
    tracker, _, _ = _tracker_with_org()

    summary = tracker.conversion_summary()

    assert set(summary.keys()) == {"upgrade_offer", "retention_offer", "expansion_offer"}


def test_conversion_summary_sem_acoes_e_tudo_pending():
    auth = PlatformAuth()
    auth.create_organization("Acme")
    tracker = LeadExecutionTracker(auth)

    summary = tracker.conversion_summary()

    assert summary["upgrade_offer"]["pending"] == 1
    assert summary["upgrade_offer"]["contacted"] == 0
    assert summary["upgrade_offer"]["converted"] == 0
    assert summary["upgrade_offer"]["ignored"] == 0
    assert summary["upgrade_offer"]["conversion_rate"] == 0.0


def test_conversion_summary_conta_estados_corretamente():
    auth = PlatformAuth()
    org_a = auth.create_organization("Acme A")
    org_b = auth.create_organization("Acme B")
    org_c = auth.create_organization("Acme C")
    org_d = auth.create_organization("Acme D")
    tracker = LeadExecutionTracker(auth)

    tracker.record_action(org_a, "upgrade_offer", "execute")
    tracker.record_action(org_b, "upgrade_offer", "convert")
    tracker.record_action(org_c, "upgrade_offer", "ignore")
    # org_d left untouched -> stays "pending"

    summary = tracker.conversion_summary()["upgrade_offer"]

    assert summary["pending"] == 1
    assert summary["contacted"] == 1
    assert summary["converted"] == 1
    assert summary["ignored"] == 1


def test_conversion_rate_exclui_pending_do_denominador():
    """3 orgs engaged with (contacted/converted/ignored), 1 converted --
    conversion_rate should be 1/3, not 1/4 (which would count the
    never-touched "pending" org too)."""
    auth = PlatformAuth()
    org_a = auth.create_organization("Acme A")
    org_b = auth.create_organization("Acme B")
    org_c = auth.create_organization("Acme C")
    auth.create_organization("Acme D (never touched)")
    tracker = LeadExecutionTracker(auth)

    tracker.record_action(org_a, "upgrade_offer", "convert")
    tracker.record_action(org_b, "upgrade_offer", "execute")
    tracker.record_action(org_c, "upgrade_offer", "ignore")

    summary = tracker.conversion_summary()["upgrade_offer"]

    assert summary["conversion_rate"] == round(1 / 3, 4)


def test_conversion_summary_sem_organizacoes_nao_gera_erro():
    auth = PlatformAuth()
    tracker = LeadExecutionTracker(auth)

    summary = tracker.conversion_summary()

    for metrics in summary.values():
        assert metrics["conversion_rate"] == 0.0
