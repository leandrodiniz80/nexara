from app.platform.metrics.webhook import WebhookClient


def test_send_para_url_invalida_nao_lanca_erro():
    client = WebhookClient("http://this-host-does-not-resolve.invalid", timeout_seconds=0.5)

    client.send({"test": 1})


def test_send_para_scheme_invalido_nao_lanca_erro():
    client = WebhookClient("not-a-url", timeout_seconds=0.5)

    client.send({"test": 1})


def test_send_serializa_payload_como_json_antes_de_falhar():
    """Non-JSON-serializable payloads must not escape as an unhandled
    exception either — the whole point of this class is that nothing it
    does can break the caller."""
    client = WebhookClient("http://this-host-does-not-resolve.invalid", timeout_seconds=0.5)

    client.send({"circular": object()})
