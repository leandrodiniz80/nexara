"""The platform's official dispatch infrastructure for public commands. It
validates that a requested command exists, validates that a handler for it
is registered, and delegates to that handler — it never executes the
domain itself, never instantiates a handler, never integrates with
anything else. Every future integration (REST, CLI, SDK, Workers,
Scheduler) is meant to go exclusively through this bus.
"""
