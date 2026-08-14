"""Decision Engine: a generic decision-making mechanism. It receives a
DecisionContext and returns a DecisionResult — nothing more. It executes
nothing and calls no other module: not Workflow, Automation, Runtime, CRM, AI,
or even Business Rules. Any module may reuse it in the future by supplying its
own DecisionContext and registering its own Strategy.
"""
