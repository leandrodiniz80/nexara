from app.repositories.prospecting.company_tag_repository import CompanyTagRepository
from app.repositories.prospecting.tag_repository import TagRepository


class TagService:
    """Owns Tag lifecycle and its assignment to companies (CompanyTag)."""

    def __init__(
        self,
        repository: TagRepository,
        company_tag_repository: CompanyTagRepository,
    ) -> None:
        self.repository = repository
        self.company_tag_repository = company_tag_repository
