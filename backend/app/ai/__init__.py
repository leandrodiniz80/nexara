"""AI Orchestrator module.

Every AI call on the platform must go through `app.ai.orchestrator.AIOrchestrator`.
No other module is allowed to import a provider (`app.ai.providers.*`) directly.
"""
