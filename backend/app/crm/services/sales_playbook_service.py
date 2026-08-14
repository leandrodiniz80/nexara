from typing import Any

from app.crm.models.crm_company import CRMCompany
from app.crm.models.crm_contact import CRMContact
from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.sales_playbook import SalesPlaybook

_DEFAULT_COMPANY_SIZE = "Qualquer"

_PLAYBOOKS_BY_SEGMENT: dict[str, dict[str, Any]] = {
    "Publicidade": {
        "name": "Cadência Comercial Padrão",
        "description": (
            "Abordagem comercial padrão, indicada para agências e empresas de publicidade."
        ),
        "target_segment": "Publicidade",
        "priority": "ALTA",
        "cadence_name": "Cadência Comercial Padrão",
        "estimated_duration": 12,
        "recommended_channels": ["E-mail", "WhatsApp", "Telefone"],
    },
    "Pet": {
        "name": "Cadência Consultiva",
        "description": (
            "Abordagem consultiva, com foco em relacionamento, indicada para o segmento pet."
        ),
        "target_segment": "Pet",
        "priority": "MÉDIA",
        "cadence_name": "Cadência Consultiva",
        "estimated_duration": 15,
        "recommended_channels": ["WhatsApp", "Telefone", "E-mail"],
    },
    "Saúde": {
        "name": "Cadência Institucional",
        "description": (
            "Abordagem formal e institucional, indicada para o segmento de saúde."
        ),
        "target_segment": "Saúde",
        "priority": "MÉDIA",
        "cadence_name": "Cadência Institucional",
        "estimated_duration": 20,
        "recommended_channels": ["E-mail", "Telefone"],
    },
    "Indústria": {
        "name": "Cadência Técnica",
        "description": (
            "Abordagem técnica, com foco em especificações e integrações, "
            "indicada para o segmento de indústria."
        ),
        "target_segment": "Indústria",
        "priority": "ALTA",
        "cadence_name": "Cadência Técnica",
        "estimated_duration": 18,
        "recommended_channels": ["E-mail", "Telefone"],
    },
}

_DEFAULT_PLAYBOOK_SPEC: dict[str, Any] = {
    "name": "Cadência Comercial Padrão",
    "description": (
        "Abordagem comercial padrão, usada quando o segmento da empresa "
        "não possui uma cadência específica associada."
    ),
    "target_segment": "Geral",
    "priority": "MÉDIA",
    "cadence_name": "Cadência Comercial Padrão",
    "estimated_duration": 12,
    "recommended_channels": ["E-mail", "WhatsApp", "Telefone"],
}


class SalesPlaybookService:
    """Recommends which commercial playbook — cadence strategy, priority and
    channels — an opportunity should follow, based solely on its company's
    segment. A fixed, deterministic lookup: no AI, no Decision Strategy, no
    Business Rule, no Runtime, no Workflow, no Automation, no Scheduler, no
    persistence, no Engine of any kind.

    It never executes and never creates anything. SalesCadenceService
    remains the only place that defines the actual sequence of contacts, and
    SalesCadenceExecutionService remains the only place that tracks progress
    through one; this class only ever recommends which strategy to use.

    `opportunity` and `contact` are accepted to match the module's full
    input contract, but the current rule set only branches on the
    company's segment — they are not yet used to vary the recommendation.
    """

    def recommend_playbook(
        self,
        opportunity: CRMOpportunity,
        company: CRMCompany,
        contact: CRMContact | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> SalesPlaybook:
        del opportunity, contact
        spec = _PLAYBOOKS_BY_SEGMENT.get(company.segment or "", _DEFAULT_PLAYBOOK_SPEC)
        return SalesPlaybook(
            name=spec["name"],
            description=spec["description"],
            target_segment=spec["target_segment"],
            company_size=_DEFAULT_COMPANY_SIZE,
            priority=spec["priority"],
            cadence_name=spec["cadence_name"],
            estimated_duration=spec["estimated_duration"],
            recommended_channels=list(spec["recommended_channels"]),
            metadata=dict(metadata or {}),
        )
