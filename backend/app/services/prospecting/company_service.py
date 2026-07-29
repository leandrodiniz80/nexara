from app.repositories.prospecting.company_repository import CompanyRepository


class CompanyService:
    def __init__(self, repository: CompanyRepository) -> None:
        self.repository = repository
