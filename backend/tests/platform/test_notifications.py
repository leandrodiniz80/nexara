"""Tests for NotificationService (Sprint 281) and BillingDecisionEngine's
notification hooks.
"""

import time

from app.platform.billing.decision_engine import BillingDecisionEngine
from app.platform.notifications.notification_service import NotificationService

_DAY = 86400


def _days_ago(n: int) -> int:
    return int(time.time()) - n * _DAY


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return dict(self._orgs)

    def get_organization(self, org_id: str) -> dict | None:
        return self._orgs.get(org_id)

    def set_organization_plan(self, org_id: str, plan: str) -> None:
        self._orgs[org_id]["plan"] = plan

    def set_retention_flag(self, org_id: str, flag: bool) -> None:
        self._orgs[org_id]["retention_flag"] = flag


class FakeAnalytics:
    def __init__(self, usage_ratios=None, scores=None, churn=None):
        self._usage_ratios = usage_ratios or {}
        self._scores = scores or {}
        self._churn = churn or []

    def usage_ratio(self, org_id, usage_metric="alerts_sent", limit_metric="alerts_per_hour"):
        return self._usage_ratios.get(org_id)

    def score_organization(self, org: dict) -> int:
        return self._scores.get(org["_id"], 0)

    def predict_churn(self) -> list[dict]:
        return self._churn


class RecordingNotifier:
    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []

    def send(self, org_id: str, notification_type: str, payload: dict) -> dict:
        self.calls.append((org_id, notification_type, payload))
        return {"sent": True, "type": notification_type, "org_id": org_id}


# --- NotificationService itself --------------------------------------------


def test_send_retorna_estrutura_correta():
    result = NotificationService().send("org_1", "upgrade_recommended", {"foo": "bar"})

    assert result == {"sent": True, "type": "upgrade_recommended", "org_id": "org_1"}


def test_send_aceita_payload_arbitrario():
    payload = {"org_id": "org_1", "action": "upgrade", "from": "free", "to": "pro"}

    result = NotificationService().send("org_1", "upgrade_recommended", payload)

    assert result["sent"] is True


# --- BillingDecisionEngine notification hooks -------------------------------


def test_envio_chamado_para_upgrade_aplicado():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    notifier = RecordingNotifier()
    engine = BillingDecisionEngine(analytics, auth, notifier=notifier)

    engine.run(execute=True)

    assert len(notifier.calls) == 1
    org_id, notification_type, payload = notifier.calls[0]
    assert org_id == "org_1"
    assert notification_type == "upgrade_recommended"
    assert payload["org_id"] == "org_1"
    assert payload["reason"] == "over_usage"


def test_envio_chamado_para_pending_checkout():
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "free",
            "created_at": _days_ago(10),
            "stripe_subscription_id": "sub_1",
        }
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    notifier = RecordingNotifier()

    class FakeStripeSync:
        def upgrade_subscription(self, org_id, target_plan):
            return {"status": "pending", "checkout_url": "https://checkout.example/x"}

    engine = BillingDecisionEngine(
        analytics, auth, stripe_sync=FakeStripeSync(), notifier=notifier
    )

    engine.run(execute=True)

    assert len(notifier.calls) == 1
    org_id, notification_type, payload = notifier.calls[0]
    assert org_id == "org_1"
    assert notification_type == "checkout_pending"
    assert payload["checkout_url"] == "https://checkout.example/x"
    assert payload["reason"] == "requires_customer_action"


def test_envio_chamado_para_churn_risk():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        churn=[{"org_id": "org_1", "risk": "high", "reason": "payment_failed"}]
    )
    notifier = RecordingNotifier()
    engine = BillingDecisionEngine(analytics, auth, notifier=notifier)

    engine.run(execute=True)

    assert len(notifier.calls) == 1
    org_id, notification_type, payload = notifier.calls[0]
    assert org_id == "org_1"
    assert notification_type == "churn_risk"
    assert payload["reason"] == "payment_failed"


def test_payload_correto_para_cada_tipo_de_evento():
    orgs = {
        "org_upgrade": {"_id": "org_upgrade", "plan": "free", "created_at": _days_ago(10)},
        "org_churn": {"_id": "org_churn", "plan": "pro"},
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        usage_ratios={"org_upgrade": 1.5},
        scores={"org_upgrade": 0, "org_churn": 0},
        churn=[{"org_id": "org_churn", "risk": "high", "reason": "payment_failed"}],
    )
    notifier = RecordingNotifier()
    engine = BillingDecisionEngine(analytics, auth, notifier=notifier)

    engine.run(execute=True)

    by_type = {call[1]: call for call in notifier.calls}
    assert by_type["upgrade_recommended"][2]["action"] == "upgrade"
    assert by_type["churn_risk"][2]["action"] == "retention_flag"


def test_nao_envia_notificacao_para_downgrade_recommendations():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro", "created_at": _days_ago(40)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.05}, scores={"org_1": 20})
    notifier = RecordingNotifier()
    engine = BillingDecisionEngine(analytics, auth, notifier=notifier)

    engine.run(execute=True)

    assert notifier.calls == []


def test_nao_envia_notificacao_durante_dry_run():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    notifier = RecordingNotifier()
    engine = BillingDecisionEngine(analytics, auth, notifier=notifier)

    engine.run(execute=False)

    assert notifier.calls == []


def test_nao_quebra_sem_notifier():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    engine = BillingDecisionEngine(analytics, auth, notifier=None)

    applied = engine.run(execute=True)

    assert len(applied["upgrades"]) == 1


def test_nao_envia_notificacao_quando_acao_e_pulada():
    """An org whose state drifted between proposal and apply never gets
    to "applied" or "pending" -- no notification for a no-op."""
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    notifier = RecordingNotifier()
    engine = BillingDecisionEngine(analytics, auth, notifier=notifier)

    orgs["org_1"]["plan"] = "pro"

    engine.run(execute=True)

    assert notifier.calls == []
