from pydantic import BaseModel, ConfigDict


class HealthReport(BaseModel):
    """The platform's frozen contract for the result of one health-check
    run — a plain, immutable value: which individual results came back,
    and whether all of them were healthy.
    """

    model_config = ConfigDict(frozen=True)

    results: tuple[bool, ...]
    healthy: bool
