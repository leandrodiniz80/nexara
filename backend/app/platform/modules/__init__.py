"""The platform's official module architecture: the Kernel no longer knows
a single, hardcoded Pipeline — it knows MODULES, each responsible for
supplying its own PipelineStages through its own StageProvider. This is
the foundation for independent modules (CRM, Runtime, AI, Automation,
Workflow, etc.) registering their stages without ever touching the
Kernel's own composition code.
"""
