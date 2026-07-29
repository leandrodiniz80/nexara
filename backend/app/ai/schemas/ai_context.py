from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mission.mission import MissionRead
from app.schemas.mission.mission_event import MissionEventRead
from app.schemas.mission.mission_metrics import MissionMetricsRead
from app.schemas.prospecting.campaign import CampaignRead
from app.schemas.prospecting.company import CompanyRead
from app.schemas.prospecting.contact import ContactRead
from app.schemas.prospecting.prospect import ProspectRead


class AIMessage(BaseModel):
    """One turn of conversational history fed to a provider's chat()."""

    role: Literal["system", "user", "assistant"]
    content: str


class AIContext(BaseModel):
    """Everything an agent needs to do its job, handed in by whatever triggers it.

    Reuses the Prospecting/Mission domains' own Read schemas instead of redefining
    shapes that already exist — this is a one-way, read-only dependency from the AI
    module onto them; nothing in Prospecting/Mission depends back on `ai/`.

    NOTE: this used to have a `mission: str | None` field meaning "what this particular
    execution should do" — now that Mission is a real platform aggregate, that field is
    renamed to `instruction` (what it always meant) to make room for the actual Mission
    below. Every prospecting action happens within a Mission, so this is the field an
    agent should reach for to know the objective/targets driving the work it's doing.
    """

    model_config = ConfigDict(from_attributes=True)

    company: CompanyRead | None = None
    campaign: CampaignRead | None = None
    prospect: ProspectRead | None = None
    contact: ContactRead | None = None
    mission: MissionRead | None = None
    mission_metrics: MissionMetricsRead | None = None
    mission_history: list[MissionEventRead] = Field(default_factory=list)
    instruction: str | None = None
    history: list[AIMessage] = Field(default_factory=list)
    memory: list[Any] = Field(default_factory=list)
    variables: dict[str, str] = Field(default_factory=dict)
