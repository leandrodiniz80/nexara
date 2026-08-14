"""Outreach Engine: generates parametrized commercial assets and takes them through
approval — no AI, no email sending, no SMTP, no APIs. An OutreachAsset may be an
email, a WhatsApp message, a proposal, a call script, a video, or anything else
AssetType names; every asset is produced from an AssetTemplate via an AssetGenerator
(AssetRenderer today); the terminal state is READY_TO_SEND, never "sent".
"""
