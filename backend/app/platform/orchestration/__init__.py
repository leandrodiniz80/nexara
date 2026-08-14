"""The platform's first official composition: PlatformExecutionOrchestrator,
the single point capable of coordinating Operations, Decision, Runtime, and
Observability together. No Engine, Coordinator, or existing factory is
altered — every wiring decision happens exclusively inside this
orchestrator, built entirely from each module's own official factories.
"""
