from pydantic import BaseModel, ConfigDict

from app.platform.features.feature_executor import FeatureExecutor


class PlatformFeatures(BaseModel):
    """The platform's official public facade for its feature subsystem —
    a frozen model holding exactly one collaborator. `features()`
    delegates exclusively to `executor.execute()` and returns exactly
    what it produced, fresh on every call. No additional logic, no
    transformation, no interpretation, no exception handling.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    executor: FeatureExecutor

    def features(self) -> tuple[bool, ...]:
        return self.executor.execute()
