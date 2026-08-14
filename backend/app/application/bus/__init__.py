"""Shared execution infrastructure for CommandBus and QueryBus — timing and
recording, nothing else. This package does not unify Command and Query:
CQRS remains fully intact, each bus keeps its own request/result contracts
and its own registry. Only the mechanics of measuring and recording one
dispatch's execution are shared, through BusExecutionService/BusExecution.
"""
