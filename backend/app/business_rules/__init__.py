"""Business Rules Engine: a generic mechanism for evaluating rules — Comparison
(Equals/GreaterThan/Contains/...), Logical (AND/OR/NOT), and Expression (raw
strings like "score >= 70"). It encodes no specific business rule and knows
nothing about CRM, Workflow, Automation, Runtime, Mission, Prospect, or AI: any
Engine may reuse it in the future by supplying its own RuleContext.
"""
