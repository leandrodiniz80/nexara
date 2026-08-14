from pydantic import BaseModel, ConfigDict


class PublicError(BaseModel):
    """One error in the platform's public contract — frozen: a plain
    code/message pair, independent of whatever internal exception or
    domain failure produced it.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
