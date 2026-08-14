import inspect
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.builders.pipeline_builder import PipelineBuilder
from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.models.crm_pipeline import CRMPipeline
from app.crm.models.enums import OpportunityStatus
from app.crm.services import sales_forecast_service
from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_forecast_service import SalesForecastService
from app.crm.services.sales_forecast_service_factory import build_default_sales_forecast_service

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _pipeline(stage_names_and_orders: list[tuple[str, int]]) -> CRMPipeline:
    stages = [
        PipelineBuilder.build_stage(name=name, order=order)
        for name, order in stage_names_and_orders
    ]
    return PipelineBuilder.build_pipeline(name="Test Pipeline", stages=stages)


def _standard_pipeline() -> CRMPipeline:
    return _pipeline(
        [
            ("Lead", 1),
            ("Contato", 2),
            ("Reunião", 3),
            ("Proposta", 4),
            ("Negociação", 5),
            ("Fechado", 6),
        ]
    )


def _opportunity(
    *,
    pipeline: CRMPipeline,
    stage_index: int = 0,
    status: OpportunityStatus = OpportunityStatus.OPEN,
    estimated_value: float = 1000.0,
) -> CRMOpportunity:
    return CRMOpportunity(
        company_id=uuid.uuid4(),
        title="Outdoor Digital",
        pipeline_id=pipeline.id,
        stage_id=pipeline.stages[stage_index].id,
        status=status,
        metadata={"estimated_value": estimated_value},
    )


def test_pipeline_vazio_returns_a_zeroed_forecast():
    service = SalesForecastService()

    forecast = service.forecast([], now=_T0)

    assert forecast.total_pipeline_value == 0.0
    assert forecast.expected_revenue == 0.0
    assert forecast.average_probability == 0.0
    assert forecast.forecast_confidence == 0.0
    assert forecast.won_value == 0.0
    assert forecast.lost_value == 0.0
    assert forecast.open_value == 0.0
    assert forecast.forecast_items == []


def test_apenas_won_has_full_probability_and_confidence():
    pipeline = _standard_pipeline()
    a = _opportunity(pipeline=pipeline, status=OpportunityStatus.WON, estimated_value=1000.0)
    b = _opportunity(pipeline=pipeline, status=OpportunityStatus.WON, estimated_value=2000.0)
    service = SalesForecastService()

    forecast = service.forecast([(a, pipeline), (b, pipeline)], now=_T0)

    assert forecast.won_value == 3000.0
    assert forecast.expected_revenue == 3000.0
    assert all(item.probability == 1.0 for item in forecast.forecast_items)
    assert all(item.confidence == 100.0 for item in forecast.forecast_items)


def test_apenas_lost_has_zero_probability_and_revenue():
    pipeline = _standard_pipeline()
    a = _opportunity(pipeline=pipeline, status=OpportunityStatus.LOST, estimated_value=1000.0)
    b = _opportunity(pipeline=pipeline, status=OpportunityStatus.LOST, estimated_value=2000.0)
    service = SalesForecastService()

    forecast = service.forecast([(a, pipeline), (b, pipeline)], now=_T0)

    assert forecast.lost_value == 3000.0
    assert forecast.expected_revenue == 0.0
    assert all(item.probability == 0.0 for item in forecast.forecast_items)
    assert all(item.confidence == 100.0 for item in forecast.forecast_items)


def test_apenas_open_derives_probability_from_the_stage_position():
    pipeline = _standard_pipeline()
    lead = _opportunity(pipeline=pipeline, stage_index=0, estimated_value=1000.0)
    negociacao = _opportunity(pipeline=pipeline, stage_index=4, estimated_value=1000.0)
    service = SalesForecastService()

    forecast = service.forecast([(lead, pipeline), (negociacao, pipeline)], now=_T0)

    lead_item = next(i for i in forecast.forecast_items if i.opportunity is lead)
    negociacao_item = next(i for i in forecast.forecast_items if i.opportunity is negociacao)
    assert lead_item.probability == pytest.approx(1 / 6)
    assert negociacao_item.probability == pytest.approx(5 / 6)
    assert forecast.open_value == 2000.0


def test_pipeline_misto_combines_won_lost_and_open():
    pipeline = _standard_pipeline()
    won = _opportunity(pipeline=pipeline, status=OpportunityStatus.WON, estimated_value=1000.0)
    lost = _opportunity(pipeline=pipeline, status=OpportunityStatus.LOST, estimated_value=500.0)
    open_ = _opportunity(pipeline=pipeline, stage_index=2, estimated_value=2000.0)
    service = SalesForecastService()

    forecast = service.forecast([(won, pipeline), (lost, pipeline), (open_, pipeline)], now=_T0)

    assert forecast.total_pipeline_value == 3500.0
    assert forecast.won_value == 1000.0
    assert forecast.lost_value == 500.0
    assert forecast.open_value == 2000.0


def test_expected_revenue_sums_each_items_expected_revenue():
    pipeline = _standard_pipeline()
    won = _opportunity(pipeline=pipeline, status=OpportunityStatus.WON, estimated_value=1000.0)
    open_ = _opportunity(pipeline=pipeline, stage_index=2, estimated_value=1200.0)
    service = SalesForecastService()

    forecast = service.forecast([(won, pipeline), (open_, pipeline)], now=_T0)

    expected_open_revenue = 1200.0 * (3 / 6)
    assert forecast.expected_revenue == pytest.approx(1000.0 + expected_open_revenue)


def test_average_probability_is_the_mean_across_items():
    pipeline = _standard_pipeline()
    won = _opportunity(pipeline=pipeline, status=OpportunityStatus.WON)
    lost = _opportunity(pipeline=pipeline, status=OpportunityStatus.LOST)
    service = SalesForecastService()

    forecast = service.forecast([(won, pipeline), (lost, pipeline)], now=_T0)

    assert forecast.average_probability == pytest.approx(0.5)


def test_forecast_confidence_is_the_mean_across_items():
    pipeline = _standard_pipeline()
    won = _opportunity(pipeline=pipeline, status=OpportunityStatus.WON)
    open_at_lead = _opportunity(pipeline=pipeline, stage_index=0)
    service = SalesForecastService()

    forecast = service.forecast([(won, pipeline), (open_at_lead, pipeline)], now=_T0)

    expected_confidence = (100.0 + (1 / 6) * 100) / 2
    assert forecast.forecast_confidence == pytest.approx(expected_confidence)


def test_pipeline_com_varios_estagios_never_hardcodes_a_stage_count():
    pipeline = _pipeline(
        [("A", 1), ("B", 2), ("C", 3), ("D", 4), ("E", 5), ("F", 6), ("G", 7), ("H", 8)]
    )
    opportunity = _opportunity(pipeline=pipeline, stage_index=3)
    service = SalesForecastService()

    forecast = service.forecast([(opportunity, pipeline)], now=_T0)

    assert forecast.forecast_items[0].probability == pytest.approx(4 / 8)


def test_pipeline_com_apenas_dois_estagios():
    pipeline = _pipeline([("Lead", 1), ("Fechado", 2)])
    opportunity = _opportunity(pipeline=pipeline, stage_index=0)
    service = SalesForecastService()

    forecast = service.forecast([(opportunity, pipeline)], now=_T0)

    assert forecast.forecast_items[0].probability == pytest.approx(0.5)


def test_imutabilidade_rejects_attribute_assignment():
    pipeline = _standard_pipeline()
    opportunity = _opportunity(pipeline=pipeline, status=OpportunityStatus.WON)
    service = SalesForecastService()

    forecast = service.forecast([(opportunity, pipeline)], now=_T0)

    with pytest.raises(ValidationError):
        forecast.expected_revenue = 999.0

    with pytest.raises(ValidationError):
        forecast.forecast_items[0].probability = 0.5


def test_build_default_sales_forecast_service_returns_a_usable_service():
    service = build_default_sales_forecast_service()
    pipeline = _standard_pipeline()
    opportunity = _opportunity(pipeline=pipeline, status=OpportunityStatus.WON)

    assert isinstance(service, SalesForecastService)
    forecast = service.forecast([(opportunity, pipeline)], now=_T0)
    assert isinstance(forecast, SalesForecast)
    assert forecast.won_value == 1000.0


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_forecast_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_forecast_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_forecast_service)
    assert "CRMEngine" not in source
