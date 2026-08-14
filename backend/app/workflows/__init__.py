"""Workflow Engine: coordinates a sequence of ApplicationTasks — nothing else. No
business rule, no AI, no database, no Provider. It only knows ApplicationTask,
TaskExecutor, TaskResult and TaskContext; everything else (which concrete tasks
exist, how they're wired) is decided by workflow_engine_factory.py, the one
composition root in this module.
"""
