"""Observability: traceability, audit, and performance recording for the platform.

This module makes no decisions and enforces no business rules — it only records
what it is told, deterministically. Nothing in the rest of the platform calls into
it yet (that integration is explicitly left for a future sprint); this module is
infrastructure only, built and tested standalone.
"""
