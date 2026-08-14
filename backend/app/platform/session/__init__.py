"""The platform's official Execution Session — the single, immutable
context every platform execution carries from start to finish. It executes
nothing and knows no domain (not Runtime, Operations, Decision, Workflow,
CRM, or Observability): it only tracks that one execution happened, when
it started, and when it finished. This is the foundation for future
authentication, multi-tenancy, distributed tracing, global timeouts,
cancellation, and context propagation — none of which this sprint adds.
"""
