from app.repositories.prospecting.interaction_repository import InteractionRepository


class InteractionService:
    def __init__(self, repository: InteractionRepository) -> None:
        self.repository = repository
