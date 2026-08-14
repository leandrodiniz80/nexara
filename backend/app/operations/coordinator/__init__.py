"""The first coordination layer of the Operations domain. It knows
exclusively OperationsEngine and OperationHistoryService — nothing about
Runtime, Workflow, CRM, Decision, Rules, Automation, Presentation,
Contracts, Application, CommandBus, or QueryBus — and only ever coordinates
one Operation's lifecycle (create -> start -> finish/fail), producing both
its resulting state and its full history. This is the single coordination
point Runtime, Application, and future Scheduler/Workers/API integrations
run operations through.
"""
