"""Decision's official consumer of the operational data Operations and
Observability already produce. OperationDecisionService assembles an
OperationDecisionContext from an OperationHistory/OperationResult/
OperationTrace — it decides nothing itself. DecisionOperationsService
adapts that context into DecisionEngine's existing public API — no new
Strategy, no change to DecisionEngine. Operations never imports Decision
in any direction; this dependency is strictly one-way.
"""
