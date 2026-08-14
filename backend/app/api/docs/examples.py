"""Example payloads shown in the OpenAPI docs for the platform's flagship routes —
the same worked example (Agência XYZ / Goiânia / João) used throughout every prior
sprint's own deliverables, so the documentation and the rest of the codebase tell
one consistent story.
"""

START_MISSION_EXAMPLE = {
    "summary": "Start a prospecting mission for ad agencies in Goiânia",
    "value": {
        "mission_name": "Expansão Goiânia",
        "segment": "Publicidade",
        "city": "Goiânia",
        "state": "GO",
        "minimum_score": 60,
        "asset_type": "email",
        "channel": "email",
        "tone": "consultivo",
    },
}

MISSION_WORKSPACE_EXAMPLE = {
    "summary": "A running mission's workspace",
    "value": {
        "success": True,
        "data": {
            "mission": {"name": "Expansão Goiânia", "status": "running", "progress": 50},
            "statistics": {
                "companies_found": 5,
                "qualified": 3,
                "prospects": 2,
                "assets_generated": 2,
                "assets_pending": 1,
            },
            "health": "healthy",
        },
        "errors": [],
        "warnings": [],
        "request_id": "b3b3c3e2-4f7a-4b3e-9a3a-2f2f2f2f2f2f",
        "execution_time": 0.0123,
        "timestamp": "2026-08-04T12:00:00Z",
    },
}

QUALIFY_PROSPECT_EXAMPLE = {
    "summary": "Qualify a retail-segment company",
    "value": {
        "profile": {"segment": "retail", "company_size": "small"},
        "company_id": "11111111-1111-1111-1111-111111111111",
    },
}

GENERATE_ASSET_EXAMPLE = {
    "summary": "Generate an email for João at Agência XYZ",
    "value": {
        "company": {
            "legal_name": "Agência XYZ Ltda",
            "trade_name": "Agência XYZ",
            "cnpj": "12345678000199",
            "segment": "Publicidade",
            "city": "Goiânia",
            "state": "GO",
        },
        "asset_type": "email",
        "tone": "consultivo",
        "contact_name": "João",
        "objective": "Conseguir reunião",
    },
}

OUTREACH_GENERATE_EXAMPLE = {
    "summary": "Generate a follow-up message from a stored template",
    "value": {
        "prospect_id": "22222222-2222-2222-2222-222222222222",
        "template_id": "33333333-3333-3333-3333-333333333333",
        "variables": {"contact_name": "João", "company": "Agência XYZ"},
    },
}

OUTREACH_APPROVE_EXAMPLE = {
    "summary": "Approve a pending asset",
    "value": {
        "asset_id": "44444444-4444-4444-4444-444444444444",
        "approved_by": "55555555-5555-5555-5555-555555555555",
    },
}
