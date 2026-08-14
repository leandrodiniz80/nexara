from app.sales_intelligence.exceptions.base import SalesIntelligenceError


class StrategyNotFoundError(SalesIntelligenceError):
    """Raised when no SalesStrategy is registered for a given CommercialSegment."""

    def __init__(self, segment: str) -> None:
        self.segment = segment
        super().__init__(f"No SalesStrategy registered for segment '{segment}'.")
