import uuid

from app.outreach.models.enums import MessageStatus
from app.outreach.models.outreach_asset import OutreachAsset


class OutreachAssetRepository:
    """In-memory store of OutreachAssets. Not explicitly named in the spec (only
    "TemplateRepository. Em memória." was) but required for OutreachEngine's own
    lifecycle to work at all: generate_message() creates one, and every later step
    (validate/submit/approve/reject/ready_to_send) needs to find that exact instance
    again — the minimal necessary addition, not an invented feature.
    """

    def __init__(self) -> None:
        self._assets: dict[uuid.UUID, OutreachAsset] = {}

    def create(self, **attrs) -> OutreachAsset:
        asset = OutreachAsset(**attrs)
        self._assets[asset.id] = asset
        return asset

    def get_by_id(self, asset_id: uuid.UUID) -> OutreachAsset | None:
        return self._assets.get(asset_id)

    def list_all(self) -> list[OutreachAsset]:
        return list(self._assets.values())

    def list_by_status(self, status: MessageStatus) -> list[OutreachAsset]:
        return [a for a in self._assets.values() if a.status == status]

    def list_by_prospect(self, prospect_id: uuid.UUID) -> list[OutreachAsset]:
        return [a for a in self._assets.values() if a.prospect_id == prospect_id]
