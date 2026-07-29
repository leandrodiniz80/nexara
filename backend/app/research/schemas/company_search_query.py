from pydantic import BaseModel, Field, model_validator


class CompanySearchQuery(BaseModel):
    """One shape for every kind of search a SearchStrategy can build — city, segment,
    CNAE and nearby searches all end up as one of these before reaching a provider.
    """

    city: str | None = None
    state: str | None = Field(None, min_length=2, max_length=2)
    segment: str | None = None
    cnae: str | None = None
    category: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    radius_km: float | None = Field(None, gt=0)
    limit: int = Field(20, gt=0, le=200)

    @model_validator(mode="after")
    def _radius_requires_coordinates(self) -> "CompanySearchQuery":
        if self.radius_km is not None and (self.latitude is None or self.longitude is None):
            raise ValueError("radius_km requires latitude and longitude to also be set")
        return self
