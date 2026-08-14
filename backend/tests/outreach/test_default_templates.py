from app.outreach.models.enums import Channel
from app.outreach.templates.default_templates import build_default_templates


def test_builds_exactly_three_active_templates():
    templates = build_default_templates()

    assert len(templates) == 3
    assert all(template.active for template in templates)


def test_templates_cover_the_three_required_categories_and_channels():
    templates = {t.category: t for t in build_default_templates()}

    assert templates["first_contact"].name == "Primeiro contato"
    assert templates["first_contact"].channel == Channel.EMAIL

    assert templates["follow_up"].name == "Follow-up"
    assert templates["follow_up"].channel == Channel.WHATSAPP
    assert templates["follow_up"].subject is None

    assert templates["meeting"].name == "Reunião"
    assert templates["meeting"].channel == Channel.EMAIL
