from pydantic import BaseModel, Field


class CommercialScore(BaseModel):
    """Output of ScoreCalculator — every component is 0-100 except conversion_probability,
    which is a percentage (also 0-100, but semantically "how likely to convert" rather
    than "how good is this factor")."""

    company_score: int = Field(..., ge=0, le=100)
    potential_score: int = Field(..., ge=0, le=100)
    urgency_score: int = Field(..., ge=0, le=100)
    visibility_score: int = Field(..., ge=0, le=100)
    relationship_score: int = Field(..., ge=0, le=100)
    conversion_probability: int = Field(..., ge=0, le=100)
    total_score: int = Field(..., ge=0, le=100)
