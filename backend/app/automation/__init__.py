"""Automation Engine: triggers Workflows automatically — nothing else. It knows
nothing about Tasks, Engines, AI, or the database; it only knows WorkflowEngine,
WorkflowRequest and WorkflowResult. Every Trigger (Manual/Scheduled/Event/
Condition) only decides whether an Automation should fire — AutomationEngine is
the only thing that ever actually runs a Workflow.
"""
