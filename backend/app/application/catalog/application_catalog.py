from pydantic import BaseModel, ConfigDict, Field

from app.application.catalog.application_operation import ApplicationOperation


class ApplicationCatalog(BaseModel):
    """The platform's frozen, complete list of discoverable public
    operations at one point in time. ApplicationCatalogService always
    returns a new one, built fresh from PublicUseCaseService's own catalog
    — never edited in place.
    """

    model_config = ConfigDict(frozen=True)

    operations: tuple[ApplicationOperation, ...] = Field(default_factory=tuple)
