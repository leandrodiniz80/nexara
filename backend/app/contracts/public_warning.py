from pydantic import BaseModel, ConfigDict


class PublicWarning(BaseModel):
    """One warning in the platform's public contract — frozen: a plain
    code/message pair, independent of whatever internal condition produced
    it.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
