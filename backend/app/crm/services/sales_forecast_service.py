from datetime import datetime, timezone

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.models.crm_pipeline import CRMPipeline
from app.crm.models.enums import OpportunityStatus
from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_forecast_item import SalesForecastItem

ForecastEntry = tuple[CRMOpportunity, CRMPipeline]

_FULL_CONFIDENCE = 100.0


class SalesForecastService:
    """Turns a list of CRMOpportunity into a deterministic revenue
    forecast — no AI, no Machine Learning, no regression, only fixed
    arithmetic. No persistence, no CRMEngine, no Runtime, no Workflow, no
    Automation, no Adapter, no Rule, no Decision.

    An OPEN opportunity's probability is never hardcoded to a fixed number
    of pipeline stages — it is always `current_stage.order / last_stage.
    order`, computed from whichever CRMPipeline the opportunity actually
    belongs to. Since CRMOpportunity only carries a bare `pipeline_id`/
    `stage_id` reference (never the CRMPipeline embedded), and this
    calculation is impossible without the pipeline's own ordered stage
    list, each entry pairs a CRMOpportunity with its CRMPipeline — the same
    kind of deliberate, documented input-shape pairing already used for
    SalesWorkQueueService and SalesPipelineIntelligenceService in earlier
    sprints.
    """

    def forecast(
        self,
        entries: list[ForecastEntry],
        *,
        now: datetime | None = None,
    ) -> SalesForecast:
        now = now or datetime.now(timezone.utc)
        items = [self._forecast_item(opportunity, pipeline) for opportunity, pipeline in entries]

        if not items:
            return SalesForecast(
                total_pipeline_value=0.0,
                expected_revenue=0.0,
                average_probability=0.0,
                forecast_confidence=0.0,
                won_value=0.0,
                lost_value=0.0,
                open_value=0.0,
                forecast_items=[],
                generated_at=now,
            )

        total_pipeline_value = sum(self._value(opportunity) for opportunity, _ in entries)
        won_value = self._value_for_status(entries, OpportunityStatus.WON)
        lost_value = self._value_for_status(entries, OpportunityStatus.LOST)
        open_value = self._value_for_status(entries, OpportunityStatus.OPEN)

        return SalesForecast(
            total_pipeline_value=total_pipeline_value,
            expected_revenue=sum(item.expected_revenue for item in items),
            average_probability=sum(item.probability for item in items) / len(items),
            forecast_confidence=sum(item.confidence for item in items) / len(items),
            won_value=won_value,
            lost_value=lost_value,
            open_value=open_value,
            forecast_items=items,
            generated_at=now,
        )

    @classmethod
    def _forecast_item(
        cls, opportunity: CRMOpportunity, pipeline: CRMPipeline
    ) -> SalesForecastItem:
        value = cls._value(opportunity)

        if opportunity.status == OpportunityStatus.WON:
            return SalesForecastItem(
                opportunity=opportunity,
                probability=1.0,
                expected_revenue=value,
                confidence=_FULL_CONFIDENCE,
                reason="Oportunidade ganha.",
            )

        if opportunity.status == OpportunityStatus.LOST:
            return SalesForecastItem(
                opportunity=opportunity,
                probability=0.0,
                expected_revenue=0.0,
                confidence=_FULL_CONFIDENCE,
                reason="Oportunidade perdida.",
            )

        return cls._open_forecast_item(opportunity, pipeline, value)

    @staticmethod
    def _open_forecast_item(
        opportunity: CRMOpportunity, pipeline: CRMPipeline, value: float
    ) -> SalesForecastItem:
        if not pipeline.stages:
            return SalesForecastItem(
                opportunity=opportunity,
                probability=0.0,
                expected_revenue=0.0,
                confidence=0.0,
                reason="Pipeline sem estágios definidos.",
            )

        stage = next((s for s in pipeline.stages if s.id == opportunity.stage_id), None)
        last_order = max(s.order for s in pipeline.stages)

        if stage is None or last_order <= 0:
            return SalesForecastItem(
                opportunity=opportunity,
                probability=0.0,
                expected_revenue=0.0,
                confidence=0.0,
                reason="Estágio da oportunidade não encontrado no pipeline.",
            )

        probability = stage.order / last_order
        return SalesForecastItem(
            opportunity=opportunity,
            probability=probability,
            expected_revenue=value * probability,
            confidence=probability * 100,
            reason=f"Estágio {stage.name} ({stage.order}/{last_order}).",
        )

    @staticmethod
    def _value(opportunity: CRMOpportunity) -> float:
        raw = opportunity.metadata.get("estimated_value", 0.0)
        return float(raw) if isinstance(raw, (int, float)) else 0.0

    @classmethod
    def _value_for_status(
        cls, entries: list[ForecastEntry], status: OpportunityStatus
    ) -> float:
        return sum(
            cls._value(opportunity) for opportunity, _ in entries if opportunity.status == status
        )
