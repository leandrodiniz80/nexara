"""The platform's Execution Pipeline: PlatformExecutionOrchestrator's own
composed sequence of PipelineStages, replacing its former fixed knowledge
of Operations/Decision/Runtime/Observability. ExecutionPipeline itself
knows none of those domains — only that it runs whatever PipelineStages
it was given, in order, threading one generic state dict through them.
Composition is now the exclusive concern of PipelineRegistry: each
domain-specific stage lives in its own file (operations_stage.py,
decision_stage.py, runtime_stage.py, observability_stage.py), registered
by pipeline_registry_factory.py. None are exported as public classes.
ExecutionPipelineFactory no longer knows any concrete PipelineStage — it
only asks a PipelineRegistry for whichever stages are registered.
"""
