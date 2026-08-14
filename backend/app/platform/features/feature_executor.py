from pydantic import BaseModel, ConfigDict

from app.platform.features.feature_manager import FeatureManager


class FeatureExecutor(BaseModel):
    """The platform's official infrastructure for running the registered
    Features — a frozen model holding exactly one collaborator.
    `execute()` walks `manager.features()` in order, calls `enabled()` on
    each, and returns those results as a tuple in the same order. No
    exception handling, no filtering, no deduplication, no discovery.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    manager: FeatureManager

    def execute(self) -> tuple[bool, ...]:
        features = self.manager.features()
        return tuple(feature.enabled() for feature in features)
