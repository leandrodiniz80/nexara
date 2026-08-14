from app.outreach.models.asset_template import AssetTemplate
from app.outreach.models.enums import Channel


def build_default_templates() -> list[AssetTemplate]:
    """The three mocked templates the spec asks for. Real content, not placeholders —
    each is meant to actually render into a usable message, which is what the worked
    example (docs/deliverable #3) exercises against all three.
    """
    first_contact = AssetTemplate(
        name="Primeiro contato",
        category="first_contact",
        channel=Channel.EMAIL,
        subject="{{contact_name}}, uma oportunidade para a {{company}}",
        body=(
            "Olá {{contact_name}},\n\n"
            "Analisamos a {{company}} e acreditamos que nossa solução pode gerar maior "
            "visibilidade em {{city}}.\n\n"
            "Empresas do segmento de {{segment}} têm alcançado ótimos resultados com "
            "nossa mídia digital indoor.\n\n"
            "Podemos agendar 15 minutos para apresentar como isso funcionaria para a "
            "{{company}}?\n\n"
            "Atenciosamente,\nEquipe Elevel"
        ),
        variables=["contact_name", "company", "city", "segment"],
    )

    follow_up = AssetTemplate(
        name="Follow-up",
        category="follow_up",
        channel=Channel.WHATSAPP,
        subject=None,
        body=(
            "Oi {{contact_name}}, tudo bem? Ainda faz sentido conversarmos sobre a "
            "proposta para a {{company}}? Fico à disposição essa semana."
        ),
        variables=["contact_name", "company"],
    )

    meeting = AssetTemplate(
        name="Reunião",
        category="meeting",
        channel=Channel.EMAIL,
        subject="Confirmação: reunião sobre a {{company}}",
        body=(
            "Olá {{contact_name}},\n\n"
            "Confirmando nossa reunião sobre a proposta para a {{company}} em {{city}}. "
            "Qualquer ajuste de horário, me avise.\n\n"
            "Até breve!"
        ),
        variables=["contact_name", "company", "city"],
    )

    return [first_contact, follow_up, meeting]
