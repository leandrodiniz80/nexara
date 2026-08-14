import uuid
from typing import Any, Sequence

from app.models.prospecting.interaction import Interaction


def _stamp(instance: Any, **attrs: Any) -> None:
    from datetime import datetime, timezone

    instance.id = uuid.uuid4()
    instance.created_at = attrs.pop("created_at", datetime.now(timezone.utc))
    instance.updated_at = instance.created_at
    for key, value in attrs.items():
        setattr(instance, key, value)


class FakeInteractionRepository:
    def __init__(self) -> None:
        self.interactions: list[Interaction] = []

    async def create(self, **attrs: Any) -> Interaction:
        interaction = Interaction()
        _stamp(interaction, **attrs)
        self.interactions.append(interaction)
        return interaction

    async def list_by_prospect(self, prospect_id: uuid.UUID) -> Sequence[Interaction]:
        return [i for i in self.interactions if i.prospect_id == prospect_id]
