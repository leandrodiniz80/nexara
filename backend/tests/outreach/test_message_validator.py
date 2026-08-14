from app.outreach.models.asset_template import AssetTemplate
from app.outreach.models.enums import Channel
from app.outreach.validators.message_validator import MessageValidator


def _template(**overrides) -> AssetTemplate:
    defaults = dict(
        name="Follow-up",
        category="follow_up",
        channel=Channel.WHATSAPP,
        subject=None,
        body="Oi {{contact_name}}, tudo bem sobre a {{company}}?",
        variables=["contact_name", "company"],
    )
    defaults.update(overrides)
    return AssetTemplate(**defaults)


def test_valid_message_has_no_issues():
    validator = MessageValidator()

    issues = validator.validate(_template(), {"contact_name": "João", "company": "XYZ"})

    assert issues == []


def test_missing_required_variable_is_reported():
    validator = MessageValidator()

    issues = validator.validate(_template(), {"contact_name": "João"})

    assert any("missing required variables" in issue for issue in issues)


def test_undeclared_placeholder_is_reported():
    validator = MessageValidator()
    template = _template(body="Oi {{contact_name}}, sobre a {{company}} em {{city}}?")

    issues = validator.validate(template, {"contact_name": "João", "company": "XYZ"})

    assert any("undeclared placeholders" in issue for issue in issues)


def test_empty_template_body_is_reported():
    validator = MessageValidator()
    template = _template(body="   ", variables=[])

    issues = validator.validate(template, {})

    assert any("empty" in issue for issue in issues)


def test_body_over_channel_limit_is_reported():
    validator = MessageValidator()
    template = _template(channel=Channel.WHATSAPP)
    long_body = "x" * 1001

    issues = validator.validate(
        template, {"contact_name": "João", "company": "XYZ"}, rendered_body=long_body
    )

    assert any("exceeding the 1000-character limit" in issue for issue in issues)


def test_body_within_channel_limit_is_not_reported():
    validator = MessageValidator()
    template = _template(channel=Channel.WHATSAPP)

    issues = validator.validate(
        template, {"contact_name": "João", "company": "XYZ"}, rendered_body="x" * 999
    )

    assert issues == []
