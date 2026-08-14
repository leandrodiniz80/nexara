from pydantic import BaseModel, ConfigDict


class KPIView(BaseModel):
    """A plain, serialization-ready view of one SalesKPI — frozen: every
    field here is a direct copy of a value SalesKPIService already
    computed, never recalculated. Built for future interfaces (API, Web,
    Mobile, PDF, HTML, Export) to consume instead of the domain object
    itself.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    value: float | str
    unit: str
    status: str
