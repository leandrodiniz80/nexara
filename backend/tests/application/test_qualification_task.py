import uuid

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import TaskValidationError
from app.application.tasks.qualification_task import QualificationTask
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.enums import CommercialSegment, CompanySize
from app.sales_intelligence.services.sales_intelligence_engine_factory import (
    build_default_sales_intelligence_engine,
)


def _profile(**overrides) -> CommercialProfile:
    defaults = dict(segment=CommercialSegment.RETAIL, company_size=CompanySize.SMALL)
    defaults.update(overrides)
    return CommercialProfile(**defaults)


def test_validate_requires_profile():
    task = QualificationTask(build_default_sales_intelligence_engine())

    with pytest.raises(TaskValidationError):
        task.validate(TaskContext(variables={}))


async def test_execute_runs_the_real_sales_intelligence_engine():
    """Uses the real SalesIntelligenceEngine (via its own composition root) — the
    task only supplies the CommercialProfile, never reimplements any scoring rule."""
    task = QualificationTask(build_default_sales_intelligence_engine())
    context = TaskContext(
        company_id=uuid.uuid4(),
        variables={"profile": _profile()},
    )

    output = await task.execute(context)

    assert output["strategy_used"] == "retail"
    assert 0 <= output["score"]["total_score"] <= 100
    assert isinstance(output["recommendations"], list)


async def test_execute_saves_result_under_company_id_reference():
    engine = build_default_sales_intelligence_engine()
    task = QualificationTask(engine)
    company_id = uuid.uuid4()
    context = TaskContext(company_id=company_id, variables={"profile": _profile()})

    await task.execute(context)

    assert engine.repository.get(company_id) is not None


async def test_rollback_is_a_documented_no_op():
    task = QualificationTask(build_default_sales_intelligence_engine())
    await task.rollback(TaskContext(variables={"profile": _profile()}))
