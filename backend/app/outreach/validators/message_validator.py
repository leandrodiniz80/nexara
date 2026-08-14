from typing import Any

from app.outreach.models.asset_template import AssetTemplate
from app.outreach.models.enums import Channel
from app.outreach.render.placeholders import extract_placeholders

_MAX_LENGTH_BY_CHANNEL: dict[Channel, int] = {
    Channel.EMAIL: 5000,
    Channel.WHATSAPP: 1000,
    Channel.LINKEDIN: 1900,
}
_DEFAULT_MAX_LENGTH = 2000


class MessageValidator:
    """Deterministic data-quality checks — no AI. Four independent checks, matching
    the spec one-to-one: required variables, unknown/undeclared placeholders, an empty
    template, and a max length (per channel, since WhatsApp/LinkedIn/email have very
    different practical limits).
    """

    def validate(
        self,
        template: AssetTemplate,
        variables: dict[str, Any],
        *,
        rendered_body: str | None = None,
    ) -> list[str]:
        issues: list[str] = []

        if not template.body or not template.body.strip():
            issues.append("template body is empty")

        declared = set(template.variables)
        provided = set(variables.keys())

        missing = declared - provided
        if missing:
            issues.append(f"missing required variables: {sorted(missing)}")

        used_placeholders = extract_placeholders(template.body)
        used_placeholders |= extract_placeholders(template.subject)
        unknown_placeholders = used_placeholders - declared
        if unknown_placeholders:
            issues.append(
                f"template references undeclared placeholders: {sorted(unknown_placeholders)}"
            )

        body_to_measure = rendered_body if rendered_body is not None else template.body
        max_length = _MAX_LENGTH_BY_CHANNEL.get(template.channel, _DEFAULT_MAX_LENGTH)
        if len(body_to_measure) > max_length:
            issues.append(
                f"message body is {len(body_to_measure)} characters, exceeding the "
                f"{max_length}-character limit for {template.channel.value}"
            )

        return issues
