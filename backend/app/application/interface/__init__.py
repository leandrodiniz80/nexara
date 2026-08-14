"""The Application layer's single public door for external consumers. It
knows exclusively PlatformInterface — nothing about CRM, Runtime,
Workflow, Presentation, or Contracts — and only ever delegates to it,
returning exactly what PlatformInterface returns.
"""
