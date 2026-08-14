import uuid

from pydantic import BaseModel, Field

from app.outreach.models.enums import Channel


class AssetTemplate(BaseModel):
    """A parametrized template for a commercial asset — `body`/`subject` carry
    `{{placeholder}}` tokens; `variables` is the closed list of names the template
    actually expects (used by MessageValidator to catch both missing and
    unknown/undeclared ones). Field names (subject/body) are unchanged from the
    previous MessageTemplate: this template still describes text to substitute,
    even though the OutreachAsset it renders into is now a generic commercial asset.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    category: str
    channel: Channel
    subject: str | None = None
    body: str
    variables: list[str] = Field(default_factory=list)
    version: int = 1
    active: bool = True
