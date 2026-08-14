from pydantic import BaseModel


class SalesCadenceStep(BaseModel):
    """One step of the platform's standard prospecting cadence — a fixed,
    deterministic definition, never recomputed per opportunity. `channel`/
    `goal` are plain descriptive strings, not a closed vocabulary: nothing
    downstream branches on their exact value.
    """

    step_number: int
    action: str
    recommended_delay: int
    channel: str
    goal: str
