from app.platform.lifecycle.lifecycle_executor import LifecycleExecutor
from app.platform.lifecycle.lifecycle_starter_factory import build_default_lifecycle_starter
from app.platform.lifecycle.lifecycle_stopper_factory import build_default_lifecycle_stopper


def build_default_lifecycle_executor() -> LifecycleExecutor:
    """Composition root for this executor. Builds both of its
    collaborators exclusively through their own official factories —
    `build_default_lifecycle_starter()` and
    `build_default_lifecycle_stopper()` — and wires them into a
    LifecycleExecutor — nothing else.
    """
    return LifecycleExecutor(
        starter=build_default_lifecycle_starter(),
        stopper=build_default_lifecycle_stopper(),
    )
