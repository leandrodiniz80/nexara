from app.repositories.prospecting.contact_repository import ContactRepository


class ContactService:
    def __init__(self, repository: ContactRepository) -> None:
        self.repository = repository
