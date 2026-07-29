import pytest

from app.ai.exceptions.prompt_exceptions import (
    MissingPromptVariableError,
    PromptNotFoundError,
    PromptVersionNotFoundError,
)
from app.ai.prompts.prompt_repository import PromptRepository


def test_register_and_render_substitutes_placeholders():
    repo = PromptRepository()
    repo.register(
        "research_company",
        "Pesquise a empresa {{company}} do segmento {{segment}} na cidade {{city}}.",
    )

    rendered = repo.render(
        "research_company",
        {"company": "Coca-Cola", "segment": "Bebidas", "city": "Goiânia"},
    )

    assert rendered == "Pesquise a empresa Coca-Cola do segmento Bebidas na cidade Goiânia."


def test_render_missing_variable_raises():
    repo = PromptRepository()
    repo.register("greet", "Ola {{name}}")

    with pytest.raises(MissingPromptVariableError):
        repo.render("greet", {})


def test_get_unknown_prompt_raises_not_found():
    repo = PromptRepository()

    with pytest.raises(PromptNotFoundError):
        repo.get_active("does_not_exist")


def test_versioning_and_activation():
    repo = PromptRepository()
    repo.register("greet", "v1 content")
    repo.register("greet", "v2 content")

    assert repo.get_active("greet").content == "v2 content"

    repo.activate_version("greet", 1)
    assert repo.get_active("greet").content == "v1 content"

    with pytest.raises(PromptVersionNotFoundError):
        repo.activate_version("greet", 99)


def test_extract_placeholders():
    placeholders = PromptRepository.extract_placeholders("{{company}} - {{segment}} - {{city}}")
    assert placeholders == {"company", "segment", "city"}
