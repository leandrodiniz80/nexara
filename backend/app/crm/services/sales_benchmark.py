from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_execution_analytics import SalesExecutionAnalytics


class SalesBenchmark(BaseModel):
    """The request for one comparison: which SalesExecutionAnalytics is
    being evaluated, and which population of SalesExecutionAnalytics it is
    being measured against. Frozen — a snapshot of what was compared,
    never edited after being built.

    `benchmark_group` is expected to be the full population under
    comparison, ordinarily including `analytics` itself (e.g. "every
    execution of this playbook, including this one"). SalesBenchmarkService
    does not require this — it tolerates a `benchmark_group` of peers only,
    adding `analytics` in for the purpose of computing statistics and a
    ranking — but including it is the natural, expected usage.
    """

    model_config = ConfigDict(frozen=True)

    analytics: SalesExecutionAnalytics
    benchmark_group: list[SalesExecutionAnalytics] = Field(default_factory=list)
