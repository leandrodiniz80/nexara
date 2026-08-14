"""The platform's official dispatch infrastructure for public queries. It
validates that a requested query is registered — this sprint, it never
executes one, since no QueryHandler infrastructure exists yet. Every
future integration (REST, CLI, SDK, Workers, Scheduler) is meant to go
exclusively through this bus.
"""
