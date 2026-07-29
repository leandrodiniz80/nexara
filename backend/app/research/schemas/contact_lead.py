from pydantic import BaseModel

from app.research.models.enums import ResearchSource


class ContactLead(BaseModel):
    """A person found while researching a company (ResearchProvider.search_contacts()).

    Deliberately not the platform's `Contact` entity — same reasoning as ResearchResult
    vs Company: promoting a lead into a real Contact is a decision for whatever calls
    this engine.
    """

    name: str
    job_title: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    source: ResearchSource
