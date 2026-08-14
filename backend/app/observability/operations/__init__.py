"""Observability's official consumer of Operations' operational history.
OperationTraceService converts an OperationHistory/OperationResult into an
OperationTrace, and ObservabilityOperationsService adapts that into
ObservabilityEngine's existing public API — no new method was added to
ObservabilityEngine to make this possible. Operations never imports
Observability in any direction; this dependency is strictly one-way.
"""
