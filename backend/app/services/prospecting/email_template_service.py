from app.repositories.prospecting.email_template_repository import EmailTemplateRepository


class EmailTemplateService:
    def __init__(self, repository: EmailTemplateRepository) -> None:
        self.repository = repository
