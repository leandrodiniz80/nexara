from app.application.tasks.base.application_task import TaskType
from app.application.tasks.copy_task import CopyTask
from app.application.tasks.followup_task import FollowupTask
from app.application.tasks.proposal_task import ProposalTask
from app.application.tasks.qualification_task import QualificationTask
from app.application.tasks.research_task import ResearchTask
from app.application.tasks.task_factory import TaskFactory, build_default_task_registry


def test_build_all_returns_one_instance_of_each_task_type():
    tasks = TaskFactory().build_all()

    assert {task.task_type for task in tasks} == set(TaskType)
    kinds = {type(task) for task in tasks}
    assert kinds == {ResearchTask, CopyTask, QualificationTask, ProposalTask, FollowupTask}


def test_copy_task_and_proposal_task_and_followup_task_share_the_same_outreach_engine():
    factory = TaskFactory()

    copy_task = factory.build_copy_task()
    proposal_task = factory.build_proposal_task()
    followup_task = factory.build_followup_task()

    assert copy_task.outreach_engine is factory.outreach_engine
    assert proposal_task.outreach_engine is factory.outreach_engine
    assert followup_task.outreach_engine is factory.outreach_engine


def test_build_default_task_registry_registers_every_task_type():
    registry = build_default_task_registry()

    assert set(registry.list_registered()) == set(TaskType)
    for task_type in TaskType:
        assert registry.get(task_type).task_type == task_type
