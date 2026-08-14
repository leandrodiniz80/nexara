from datetime import datetime

from pydantic import BaseModel, Field

from app.crm.services.sales_work_queue_item import SalesWorkQueueItem


class SalesWorkQueue(BaseModel):
    """What SalesWorkQueueService.build_queue() returns — a deterministically
    ordered, already-bucketed view over a collection of ActionPlans. Nothing
    here is persisted or executed; it is a read-only snapshot as of
    `generated_at`. `warnings` carries forward every warning any input
    ActionPlan already had, plus a note for any plan this queue had to skip
    (a failed plan, or one recommending no action at all).
    """

    items: list[SalesWorkQueueItem]
    total_items: int
    high_priority: int
    medium_priority: int
    low_priority: int
    overdue_items: int
    today_items: int
    future_items: int
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)
