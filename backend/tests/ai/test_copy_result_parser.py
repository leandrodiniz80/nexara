import json

import pytest

from app.ai.agents.copy.copy_context_builder import CopyContext
from app.ai.agents.copy.copy_result_parser import CopyResultParser
from app.ai.exceptions.agent_exceptions import AgentExecutionError
from app.ai.providers.base.schemas import ProviderResponse
from app.outreach.models.enums import AssetType


def _context(**overrides) -> CopyContext:
    defaults = dict(asset_type=AssetType.EMAIL, tone="consultivo", language="pt-BR")
    defaults.update(overrides)
    return CopyContext(**defaults)


def test_parses_well_formed_json_response():
    parser = CopyResultParser()
    response = ProviderResponse(
        content=json.dumps(
            {
                "title": "João, uma oportunidade para a Agência XYZ",
                "content": "Olá João, ...",
                "metadata": {"confidence": "high"},
            }
        ),
        model="mock-1",
    )

    rendered = parser.parse(response, _context())

    assert rendered.title == "João, uma oportunidade para a Agência XYZ"
    assert rendered.content == "Olá João, ..."
    assert rendered.metadata["confidence"] == "high"
    assert rendered.metadata["asset_type"] == "email"
    assert rendered.metadata["tone"] == "consultivo"


def test_falls_back_to_raw_content_when_response_is_not_json():
    parser = CopyResultParser()
    response = ProviderResponse(content="[mock:generate] some plain text", model="mock-1")

    rendered = parser.parse(response, _context())

    assert rendered.title is None
    assert rendered.content == "[mock:generate] some plain text"
    assert rendered.metadata["asset_type"] == "email"


def test_falls_back_when_json_is_valid_but_has_no_content_key():
    parser = CopyResultParser()
    response = ProviderResponse(content=json.dumps({"foo": "bar"}), model="mock-1")

    rendered = parser.parse(response, _context())

    assert rendered.content == json.dumps({"foo": "bar"})


def test_empty_response_raises():
    parser = CopyResultParser()
    response = ProviderResponse(content="   ", model="mock-1")

    with pytest.raises(AgentExecutionError):
        parser.parse(response, _context())


def test_from_agent_payload_reconstructs_rendered_asset():
    payload = {"title": "Assunto", "content": "Corpo", "metadata": {"tone": "consultivo"}}

    rendered = CopyResultParser.from_agent_payload(payload)

    assert rendered.title == "Assunto"
    assert rendered.content == "Corpo"
    assert rendered.metadata == {"tone": "consultivo"}
