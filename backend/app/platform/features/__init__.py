"""The platform's official feature registration infrastructure: Feature,
the contract a future platform functionality implements to describe
whether it's enabled, and FeatureRegistry, the frozen registry of
published Features. This package executes nothing — no discovery, no
manager, no executor — only the contract and its registry exist here.
"""
