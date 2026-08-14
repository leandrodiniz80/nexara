"""Application layer: the bridge between Workflow, Jobs, AI, Outreach, Research, and
Sales Intelligence. Nothing here implements business rules — every ApplicationTask
only calls into whichever of those modules already does, and returns a TaskResult.
"""
