from pydantic import BaseModel, ConfigDict

from app.platform.features.feature import Feature
from app.platform.features.feature_registry import FeatureRegistry


class FeatureManager(BaseModel):
    """An intermediate layer over FeatureRegistry — a frozen model holding
    exactly one collaborator. It never runs or discovers a feature, and
    never caches or memoizes anything itself: every method is a direct,
    single-line delegation to `registry`, nothing more.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    registry: FeatureRegistry

    def feature(self, name: str) -> Feature | None:
        return self.registry.find(name)

    def exists(self, name: str) -> bool:
        return self.registry.exists(name)

    def features(self) -> list[Feature]:
        return self.registry.list()
