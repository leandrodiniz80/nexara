from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import (
    Channel,
    CommercialSegment,
    CommunicationStyle,
    GeographicScope,
    Level,
    Priority,
)
from app.sales_intelligence.models.recommendation import Recommendation

_PRODUCTS_BY_SEGMENT: dict[CommercialSegment, list[str]] = {
    CommercialSegment.RETAIL: ["Painel digital em ponto de venda", "Campanha de mídia local"],
    CommercialSegment.HEALTHCARE: [
        "Sinalização digital em recepção",
        "Campanha de autoridade médica",
    ],
    CommercialSegment.REAL_ESTATE: [
        "Totem digital em estande de vendas",
        "Campanha geolocalizada",
    ],
    CommercialSegment.AUTOMOTIVE: ["Painel em concessionária", "Campanha de test drive"],
    CommercialSegment.EDUCATION: ["Painel em campus", "Campanha de captação de matrículas"],
    CommercialSegment.PET: ["Painel em pet shop parceiro", "Campanha de fidelização"],
    CommercialSegment.SHOPPING: ["Rede de painéis no shopping", "Campanha sazonal"],
    CommercialSegment.FRANCHISE: [
        "Pacote multi-unidade",
        "Campanha de padronização de marca",
    ],
    CommercialSegment.CORPORATE: ["Sinalização corporativa", "Campanha institucional B2B"],
}

_APPROACH_BY_COMMUNICATION_STYLE: dict[CommunicationStyle, str] = {
    CommunicationStyle.FORMAL: "Abordagem consultiva e formal, com apresentação estruturada.",
    CommunicationStyle.CASUAL: "Abordagem direta e informal, focada em benefícios rápidos.",
    CommunicationStyle.TECHNICAL: "Abordagem técnica, com dados e especificações detalhadas.",
    CommunicationStyle.RELATIONSHIP_DRIVEN: (
        "Abordagem baseada em relacionamento, com contato pessoal antes da proposta."
    ),
}

_BEST_TIME_BY_SEGMENT: dict[CommercialSegment, str] = {
    CommercialSegment.RETAIL: (
        "Tarde (14h-17h), fora do horário de pico de atendimento ao cliente."
    ),
    CommercialSegment.HEALTHCARE: "Início da manhã (8h-9h), antes do início dos atendimentos.",
    CommercialSegment.REAL_ESTATE: "Fim de tarde (17h-19h), após visitas a imóveis.",
    CommercialSegment.AUTOMOTIVE: "Meio da manhã (10h-11h).",
    CommercialSegment.EDUCATION: "Início da tarde (13h-14h), fora do horário de aula.",
    CommercialSegment.PET: "Manhã (9h-11h), início do expediente.",
    CommercialSegment.SHOPPING: "Meio de semana, período comercial (10h-16h).",
    CommercialSegment.FRANCHISE: (
        "Manhã (9h-11h), preferencialmente em dia de reunião de franqueados."
    ),
    CommercialSegment.CORPORATE: (
        "Manhã (9h-11h) em dias úteis, fora de datas de fechamento mensal."
    ),
}


def priority_from_score(score: CommercialScore) -> Priority:
    if score.total_score >= 75 or score.urgency_score >= 75:
        return Priority.URGENT
    if score.total_score >= 55:
        return Priority.HIGH
    if score.total_score >= 30:
        return Priority.NORMAL
    return Priority.LOW


class RecommendationEngine:
    """Deterministic, rule-of-thumb recommendations — no AI, no external calls. Every
    `recommend_*` method is a pure function of a CommercialProfile (and, where the
    decision needs it, a CommercialScore); `build_recommendations()` is the one
    addition beyond the six named methods, needed to actually assemble Recommendation
    entities (the six methods return raw values — str/Channel — not entities).
    """

    def recommend_products(self, profile: CommercialProfile) -> list[str]:
        products = list(
            _PRODUCTS_BY_SEGMENT.get(profile.segment, ["Solução institucional de mídia"])
        )
        if profile.digital_presence in (Level.NONE, Level.LOW):
            products.append("Pacote de estruturação de presença digital")
        return products

    def recommend_approach(self, profile: CommercialProfile) -> str:
        return _APPROACH_BY_COMMUNICATION_STYLE[profile.communication_style]

    def recommend_channel(self, profile: CommercialProfile) -> Channel:
        if profile.communication_style == CommunicationStyle.RELATIONSHIP_DRIVEN:
            if profile.geographic_scope == GeographicScope.LOCAL:
                return Channel.IN_PERSON
            return Channel.PHONE
        if profile.segment == CommercialSegment.CORPORATE:
            return Channel.LINKEDIN
        if profile.social_presence in (Level.MEDIUM, Level.HIGH):
            return Channel.WHATSAPP
        return Channel.EMAIL

    def recommend_best_time(self, profile: CommercialProfile) -> str:
        return _BEST_TIME_BY_SEGMENT.get(
            profile.segment, "Período comercial (9h-18h) em dias úteis."
        )

    def recommend_followup(self, score: CommercialScore) -> str:
        if score.urgency_score >= 70:
            return "Follow-up em 1 dia útil"
        if score.urgency_score >= 45:
            return "Follow-up em 3 dias úteis"
        if score.urgency_score >= 20:
            return "Follow-up em 7 dias"
        return "Follow-up em 14 dias"

    def recommend_cta(self, profile: CommercialProfile, score: CommercialScore) -> str:
        if score.total_score >= 70:
            return "Agendar reunião de apresentação de proposta"
        if score.total_score >= 40:
            return "Agendar uma conversa exploratória de 15 minutos"
        return "Enviar material institucional para aquecimento"

    def build_recommendations(
        self, profile: CommercialProfile, score: CommercialScore
    ) -> list[Recommendation]:
        priority = priority_from_score(score)
        products = self.recommend_products(profile)
        approach = self.recommend_approach(profile)
        channel = self.recommend_channel(profile)
        best_time = self.recommend_best_time(profile)
        followup = self.recommend_followup(score)
        cta = self.recommend_cta(profile, score)

        return [
            Recommendation(
                title=f"Oferecer: {products[0]}",
                description=(
                    f"Produtos sugeridos para o segmento '{profile.segment.value}': "
                    f"{', '.join(products)}."
                ),
                priority=priority,
                confidence=score.conversion_probability,
                reason=(
                    f"Segmento '{profile.segment.value}' com maturidade de marketing "
                    f"'{profile.marketing_maturity.value}'."
                ),
            ),
            Recommendation(
                title=f"Abordar via {channel.value}",
                description=f"{approach} Melhor horário de contato: {best_time}",
                priority=priority,
                confidence=score.conversion_probability,
                reason=(
                    f"Estilo de comunicação '{profile.communication_style.value}' e presença "
                    f"social '{profile.social_presence.value}'."
                ),
            ),
            Recommendation(
                title=cta,
                description=followup,
                priority=priority,
                confidence=score.total_score,
                reason=f"Pontuação total {score.total_score} e urgência {score.urgency_score}.",
            ),
        ]
