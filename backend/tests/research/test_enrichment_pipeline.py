from app.research.models.enums import ResearchSource
from app.research.models.research_result import ResearchResult
from app.research.services.enrichment_pipeline import EnrichmentPipeline

VALID_CNPJ = "11.222.333/0001-81"
INVALID_CNPJ = "11.222.333/0001-80"


def test_normalize_cleans_up_fields():
    pipeline = EnrichmentPipeline()
    dirty = ResearchResult(
        company_name="  Empresa Teste  ",
        cnpj=VALID_CNPJ,
        website="  HTTPS://Empresa.COM  ",
        state=" go ",
        city="  Goiânia ",
        emails=[" Contato@Empresa.com "],
        phones=["(62) 99999-9999"],
        source=ResearchSource.GOOGLE_MAPS,
    )

    normalized = pipeline.normalize(dirty)

    assert normalized.company_name == "Empresa Teste"
    assert normalized.cnpj == "11222333000181"
    assert normalized.website == "https://empresa.com"
    assert normalized.state == "GO"
    assert normalized.city == "Goiânia"
    assert normalized.emails == ["contato@empresa.com"]
    assert normalized.phones == ["62999999999"]
    # normalize() returns a copy — the original is untouched
    assert dirty.company_name == "  Empresa Teste  "


def test_validate_flags_invalid_cnpj_missing_state_and_bad_email():
    pipeline = EnrichmentPipeline()
    result = ResearchResult(
        company_name="Empresa Teste",
        cnpj=INVALID_CNPJ,
        emails=["not-an-email"],
        city="Goiânia",
        source=ResearchSource.GOOGLE_MAPS,
    )

    issues = pipeline.validate(result)

    assert any("cnpj" in issue for issue in issues)
    assert any("email" in issue for issue in issues)
    assert any("state" in issue for issue in issues)


def test_validate_passes_a_clean_result():
    pipeline = EnrichmentPipeline()
    result = ResearchResult(
        company_name="Empresa Teste",
        cnpj=VALID_CNPJ,
        emails=["contato@empresa.com"],
        city="Goiânia",
        state="GO",
        source=ResearchSource.GOOGLE_MAPS,
    )

    assert pipeline.validate(result) == []


def test_enrich_merges_a_primary_and_a_supplementary_source():
    pipeline = EnrichmentPipeline()
    primary = ResearchResult(
        company_name="Empresa Teste",
        website="https://empresa.com",
        source=ResearchSource.GOOGLE_MAPS,
    )
    supplementary = ResearchResult(
        company_name="Empresa Teste",
        instagram="@empresateste",
        source=ResearchSource.INSTAGRAM,
    )

    enriched = pipeline.enrich(primary, supplementary)

    assert enriched.website == "https://empresa.com"
    assert enriched.instagram == "@empresateste"
    assert enriched.source == ResearchSource.GOOGLE_MAPS
