from typing import Any

from pydantic import BaseModel, ConfigDict

from app.platform.lifecycle.lifecycle_starter import LifecycleStarter
from app.platform.lifecycle.lifecycle_stopper import LifecycleStopper


class LifecycleExecutor(BaseModel):
    """The platform's official layer for executing lifecycle operations —
    a frozen model holding exactly two collaborators. `start()` delegates
    exclusively to `starter.start_all()`; `stop()` delegates exclusively
    to `stopper.stop_all()`. Each returns exactly what its collaborator
    returned, with no additional logic. No `restart()` exists here.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    starter: LifecycleStarter
    stopper: LifecycleStopper

    def start(self) -> Any:
        return self.starter.start_all()

    def stop(self) -> Any:
        return self.stopper.stop_all()
