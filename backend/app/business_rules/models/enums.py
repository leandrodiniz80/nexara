import enum


class RuleType(str, enum.Enum):
    """What kind of BusinessRule this is — which shape its own fields follow and
    which Evaluator in app.business_rules.evaluators handles it."""

    COMPARISON = "comparison"
    LOGICAL = "logical"
    EXPRESSION = "expression"


class ComparisonOperator(str, enum.Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_THAN = "less_than"
    LESS_OR_EQUAL = "less_or_equal"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class LogicalOperator(str, enum.Enum):
    AND = "and"
    OR = "or"
    NOT = "not"
