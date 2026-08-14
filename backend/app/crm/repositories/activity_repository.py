import uuid

from app.crm.models.crm_activity import CRMActivity


class ActivityRepository:
    """In-memory store of every CRMActivity."""

    def __init__(self) -> None:
        self._activities: dict[uuid.UUID, CRMActivity] = {}

    def save_activity(self, activity: CRMActivity) -> CRMActivity:
        self._activities[activity.id] = activity
        return activity

    def get_activity(self, activity_id: uuid.UUID) -> CRMActivity | None:
        return self._activities.get(activity_id)

    def list_activities(self, *, opportunity_id: uuid.UUID | None = None) -> list[CRMActivity]:
        activities = list(self._activities.values())
        if opportunity_id is not None:
            activities = [a for a in activities if a.opportunity_id == opportunity_id]
        return activities
