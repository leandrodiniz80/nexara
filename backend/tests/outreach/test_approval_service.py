import uuid

import pytest

from app.outreach.approval.approval_service import ApprovalService
from app.outreach.exceptions.transition_exceptions import InvalidMessageTransitionError
from app.outreach.models.enums import AssetType, Channel, MessageStatus
from app.outreach.models.outreach_asset import OutreachAsset


def _asset(**overrides) -> OutreachAsset:
    defaults = dict(
        prospect_id=uuid.uuid4(),
        template_id=uuid.uuid4(),
        asset_type=AssetType.EMAIL,
        title="Assunto",
        content="Corpo",
        channel=Channel.EMAIL,
    )
    defaults.update(overrides)
    return OutreachAsset(**defaults)


def test_submit_moves_draft_to_pending_approval():
    service = ApprovalService()
    asset = service.submit(_asset())

    assert asset.status == MessageStatus.PENDING_APPROVAL


def test_approve_stamps_approved_at_and_approved_by():
    service = ApprovalService()
    asset = service.submit(_asset())
    approver = uuid.uuid4()

    asset = service.approve(asset, approved_by=approver)

    assert asset.status == MessageStatus.APPROVED
    assert asset.approved_at is not None
    assert asset.approved_by == approver


def test_reject_moves_pending_approval_to_rejected():
    service = ApprovalService()
    asset = service.submit(_asset())

    asset = service.reject(asset, reason="tom incorreto")

    assert asset.status == MessageStatus.REJECTED


def test_reopen_moves_rejected_back_to_draft_and_clears_approval_fields():
    service = ApprovalService()
    asset = service.reject(service.submit(_asset()))

    asset = service.reopen(asset)

    assert asset.status == MessageStatus.DRAFT
    assert asset.approved_at is None
    assert asset.approved_by is None


def test_cannot_submit_an_asset_that_is_not_draft():
    service = ApprovalService()
    asset = service.submit(_asset())

    with pytest.raises(InvalidMessageTransitionError):
        service.submit(asset)


def test_cannot_approve_a_draft_asset():
    service = ApprovalService()

    with pytest.raises(InvalidMessageTransitionError):
        service.approve(_asset())


def test_cannot_reopen_an_asset_that_is_not_rejected():
    service = ApprovalService()

    with pytest.raises(InvalidMessageTransitionError):
        service.reopen(_asset())


def test_approval_pipeline_works_identically_for_a_non_text_asset_type():
    """Proves ApprovalService doesn't care what kind of asset it's approving — a
    VIDEO asset (no channel, arbitrary metadata) goes through the exact same state
    machine as an EMAIL asset."""
    service = ApprovalService()
    video_asset = _asset(
        asset_type=AssetType.VIDEO,
        channel=None,
        title=None,
        content="s3://bucket/prospect-pitch.mp4",
        metadata={"duration_seconds": 45, "resolution": "1080p"},
    )

    asset = service.approve(service.submit(video_asset), approved_by=uuid.uuid4())

    assert asset.status == MessageStatus.APPROVED
    assert asset.asset_type == AssetType.VIDEO
