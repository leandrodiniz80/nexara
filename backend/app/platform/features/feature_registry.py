from pydantic import BaseModel, ConfigDict, Field

from app.platform.features.feature import Feature
from app.shared.registry.registry import Registry


class FeatureRegistry(BaseModel):
    """The platform's frozen registry of Features — pure lookup, nothing
    else: it never runs a feature, never knows any concrete feature's
    domain, and never mutates in place. Implemented exclusively by
    encapsulating a generic Registry[Feature] — no reimplementation of
    register/register_many/find/exists/list.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    features: tuple[Feature, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[Feature]:
        return Registry(items=self.features, key=lambda feature: feature.name())

    def register(self, feature: Feature) -> "FeatureRegistry":
        return FeatureRegistry(
            features=tuple(self._as_registry().register(feature).list())
        )

    def register_many(self, features: list[Feature]) -> "FeatureRegistry":
        return FeatureRegistry(
            features=tuple(self._as_registry().register_many(features).list())
        )

    def find(self, name: str) -> Feature | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def list(self) -> list[Feature]:
        return self._as_registry().list()
