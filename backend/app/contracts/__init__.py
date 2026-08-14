"""The platform's public contract: exactly what any external consumer may
receive, independent of how it was produced. This module knows nothing
about the domain (Runtime, Workflow, CRM, Decision, Rules, Automation,
Application) and nothing about the Presentation layer (PresentationFacade,
ResponseEnvelope, ExecutivePayload) — it is a standalone definition. The
link between ResponseEnvelope and PublicResponse is future work, left to a
dedicated mapper.
"""
