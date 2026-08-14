"""The platform's official event registration infrastructure: PlatformEvent,
the contract a future event implements, and EventRegistry, the frozen
registry of published PlatformEvents. This package executes nothing —
no EventBus, no Dispatcher, no Publisher, no Subscriber — only the
contract and its registry exist here.
"""
