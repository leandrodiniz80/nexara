from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_forecast_item import SalesForecastItem


class SalesForecast(BaseModel):
    """The frozen, pipeline-wide revenue forecast — how much value is in
    play, how much of it is realistically expected, and the per-opportunity
    breakdown behind those numbers. SalesForecastService always returns a
    new one; it never edits a previous SalesForecast in place.
    """

    model_config = ConfigDict(frozen=True)

    total_pipeline_value: float
    expected_revenue: float
    average_probability: float
    forecast_confidence: float
    won_value: float
    lost_value: float
    open_value: float
    forecast_items: list[SalesForecastItem] = Field(default_factory=list)
    generated_at: datetime
