"""Execution Runtime: the single point responsible for executing any operation on
the platform — Workflows and Automations today, Jobs/Pipelines/Agents/UseCases/
Tasks in the future, all through the same public API. RuntimeEngine itself never
imports WorkflowEngine or AutomationEngine directly; it only ever talks to
ExecutorRegistry, which dispatches to whichever registered Executor supports the
requested ExecutionType.
"""
