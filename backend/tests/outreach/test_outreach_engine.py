import uuid

import pytest

from app.outreach.exceptions.template_exceptions import TemplateNotFoundError
from app.outreach.exceptions.transition_exceptions import InvalidMessageTransitionError
from app.outreach.exceptions.validation_exceptions import MessageValidationError
from app.outreach.models.enums import AssetType, MessageStatus
from app.outreach.schemas.generation_request import GenerationRequest
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine


def _request(engine, category: str, variables: dict) -> GenerationRequest:
    template = engine.template_repository.get_active_by_category(category)
    return GenerationRequest(
        prospect_id=uuid.uuid4(), template_id=template.id, variables=variables
    )


def test_generate_message_renders_the_template_and_starts_as_draft():
    engine = build_default_outreach_engine()
    request = _request(
        engine,
        "first_contact",
        {
            "contact_name": "João",
            "company": "Agência XYZ",
            "city": "Goiânia",
            "segment": "publicidade",
        },
    )

    asset = engine.generate_message(request)

    assert asset.status == MessageStatus.DRAFT
    assert asset.asset_type == AssetType.EMAIL
    assert asset.title == "João, uma oportunidade para a Agência XYZ"
    assert asset.content.startswith(
        "Olá João,\n\n"
        "Analisamos a Agência XYZ e acreditamos que nossa solução pode gerar maior "
        "visibilidade em Goiânia.\n\n"
    )


def test_generate_message_with_unknown_template_id_raises():
    engine = build_default_outreach_engine()
    request = GenerationRequest(
        prospect_id=uuid.uuid4(), template_id=uuid.uuid4(), variables={}
    )

    with pytest.raises(TemplateNotFoundError):
        engine.generate_message(request)


def test_full_lifecycle_from_generation_to_ready_to_send():
    engine = build_default_outreach_engine()
    request = _request(
        engine,
        "follow_up",
        {"contact_name": "João", "company": "Agência XYZ"},
    )

    asset = engine.generate_message(request)
    asset = engine.submit_for_approval(asset)
    assert asset.status == MessageStatus.PENDING_APPROVAL

    asset = engine.approve(asset, approved_by=uuid.uuid4())
    assert asset.status == MessageStatus.APPROVED

    asset = engine.ready_to_send(asset)
    assert asset.status == MessageStatus.READY_TO_SEND


def test_submit_for_approval_raises_when_variables_are_missing():
    engine = build_default_outreach_engine()
    request = _request(engine, "meeting", {"contact_name": "João"})

    asset = engine.generate_message(
        GenerationRequest(
            prospect_id=request.prospect_id,
            template_id=request.template_id,
            variables={"contact_name": "João", "company": "Agência XYZ", "city": "Goiânia"},
        )
    )
    asset.metadata = {"contact_name": "João"}

    with pytest.raises(MessageValidationError):
        engine.submit_for_approval(asset)


def test_ready_to_send_requires_approved_status():
    engine = build_default_outreach_engine()
    request = _request(
        engine, "follow_up", {"contact_name": "João", "company": "Agência XYZ"}
    )
    asset = engine.generate_message(request)

    with pytest.raises(InvalidMessageTransitionError):
        engine.ready_to_send(asset)


def test_reject_then_reopen_allows_a_second_submission():
    engine = build_default_outreach_engine()
    request = _request(
        engine, "follow_up", {"contact_name": "João", "company": "Agência XYZ"}
    )
    asset = engine.generate_message(request)
    asset = engine.submit_for_approval(asset)
    asset = engine.reject(asset, reason="tom incorreto")
    assert asset.status == MessageStatus.REJECTED

    asset = engine.approval_service.reopen(asset)
    asset = engine.submit_for_approval(asset)

    assert asset.status == MessageStatus.PENDING_APPROVAL


def test_generated_asset_records_which_generator_produced_it():
    engine = build_default_outreach_engine()
    request = _request(
        engine, "follow_up", {"contact_name": "João", "company": "Agência XYZ"}
    )

    asset = engine.generate_message(request)

    assert asset.generated_by == "AssetRenderer"
