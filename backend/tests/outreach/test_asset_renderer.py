import pytest

from app.outreach.exceptions.template_exceptions import MissingTemplateVariableError
from app.outreach.models.asset_template import AssetTemplate
from app.outreach.models.enums import Channel
from app.outreach.render.asset_renderer import AssetRenderer


def _template(**overrides) -> AssetTemplate:
    defaults = dict(
        name="Primeiro contato",
        category="first_contact",
        channel=Channel.EMAIL,
        subject="{{contact_name}}, uma oportunidade para a {{company}}",
        body="Olá {{contact_name}}, falamos da {{company}}.",
        variables=["contact_name", "company"],
    )
    defaults.update(overrides)
    return AssetTemplate(**defaults)


def test_substitutes_every_placeholder_in_subject_and_body():
    renderer = AssetRenderer()
    rendered = renderer.generate(
        _template(), {"contact_name": "João", "company": "Agência XYZ"}
    )

    assert rendered.title == "João, uma oportunidade para a Agência XYZ"
    assert rendered.content == "Olá João, falamos da Agência XYZ."


def test_subject_is_none_when_template_has_no_subject():
    renderer = AssetRenderer()
    rendered = renderer.generate(
        _template(subject=None, body="Oi {{contact_name}}"), {"contact_name": "João"}
    )

    assert rendered.title is None
    assert rendered.content == "Oi João"


def test_missing_variable_raises_defensively():
    renderer = AssetRenderer()

    with pytest.raises(MissingTemplateVariableError):
        renderer.generate(_template(), {"contact_name": "João"})
