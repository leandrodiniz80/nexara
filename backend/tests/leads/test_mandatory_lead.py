from types import SimpleNamespace

from app.services.leads.workday_engine import (
    derive_required_action_and_reason,
    get_next_mandatory_lead,
    is_required_action_executable,
)


def _lead(name, action_type="send_message", ready_message="Olá!", risk="low", delay=None):
    # get_next_mandatory_lead()/is_required_action_executable() only read
    # these attributes off LeadResponse, so a plain namespace stands in.
    return SimpleNamespace(
        name=name,
        next_best_action_type=action_type,
        ready_to_send_message=ready_message,
        deal_risk_level=risk,
        response_delay_minutes=delay,
    )


def test_send_message_needs_a_ready_message():
    assert is_required_action_executable(_lead("a"))
    assert not is_required_action_executable(_lead("a", ready_message=None))


def test_monitor_falls_back_to_send_message_which_is_not_executable():
    lead = _lead("a", action_type="monitor", ready_message=None)
    assert derive_required_action_and_reason(lead)[0] == "send_message"
    assert not is_required_action_executable(lead)


def test_call_and_meeting_are_always_executable():
    assert is_required_action_executable(_lead("a", action_type="call_now", ready_message=None))
    assert is_required_action_executable(
        _lead("a", action_type="schedule_meeting", ready_message=None)
    )


def test_critical_lead_without_executable_action_is_skipped():
    stuck = _lead("stuck", risk="critical", ready_message=None)
    ok = _lead("ok", risk="critical")
    assert get_next_mandatory_lead([stuck, ok]) is ok


def test_fallback_is_first_executable_lead():
    stuck = _lead("stuck", action_type="monitor", ready_message=None)
    ok = _lead("ok", action_type="call_now", ready_message=None)
    assert get_next_mandatory_lead([stuck, ok]) is ok


def test_no_executable_lead_means_nothing_is_blocked():
    queue = [
        _lead("a", action_type="monitor", ready_message=None, risk="critical"),
        _lead("b", ready_message=None, delay=500),
    ]
    assert get_next_mandatory_lead(queue) is None
    assert get_next_mandatory_lead([]) is None
