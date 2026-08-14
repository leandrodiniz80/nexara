"""Job Engine: the platform's execution layer.

Every long-running execution (search companies, generate emails, run AI, generate
proposals, import a CSV, run a workflow) is represented as a Job and run through a
JobExecutor — never invoked directly. This module knows nothing about what any
specific pipeline/workflow/AI call actually does; PipelineJobExecutor adapts any of
them generically, by shape (an async `execute(context)` method), not by import.
"""
