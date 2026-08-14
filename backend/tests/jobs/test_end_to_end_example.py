"""The worked example from the task: Criar Job -> Executar LeadDiscoveryPipeline ->
Atualizar progresso -> Finalizar Job — using the *real* LeadDiscoveryPipeline (from
Fase 2) against MockProvider, run only through a JobExecutor, never called directly.

Reuses the exact same "Pesquisar agências em Goiânia" scenario and hand-traced numbers
(35 found, 33 valid, 4 duplicates removed, 29 final companies, average score 59.66)
from tests/research/pipeline/test_lead_discovery_pipeline.py — same MockProvider,
same math, now reached through the Job layer instead of a direct pipeline.execute() call.
"""

from app.jobs.executors.pipeline_job_executor import PipelineJobExecutor
from app.jobs.models.enums import JobStatus
from app.jobs.models.job import Job
from app.jobs.repositories.job_repository import JobRepository
from app.jobs.services.job_engine_factory import build_default_job_engine
from app.research.models.enums import ResearchSource
from app.research.pipeline.factory import build_default_lead_discovery_pipeline
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.strategy_kind import StrategyKind
from app.research.providers.mock_provider import MockProvider


def _context_from_job(job: Job) -> PipelineContext:
    """Translates a generic Job into the shape LeadDiscoveryPipeline actually needs —
    this glue lives here, in the test/integration layer, never inside either module."""
    return PipelineContext(
        mission_id=job.mission_id,
        strategy=StrategyKind(job.metadata["strategy"]),
        query=job.metadata["query"],
    )


async def test_create_job_run_lead_discovery_pipeline_track_progress_finish():
    job_engine = build_default_job_engine(repository=JobRepository())
    pipeline = build_default_lead_discovery_pipeline(
        providers={ResearchSource.MOCK: MockProvider(result_count=35)},
    )
    executor = PipelineJobExecutor(
        pipeline, context_factory=_context_from_job, job_engine=job_engine
    )

    # Step 1: Criar Job
    job = job_engine.create(
        job_type="lead_discovery",
        pipeline_name="LeadDiscoveryPipeline",
        metadata={
            "strategy": "city",
            "query": {"city": "Goiânia", "state": "GO", "category": "Agência", "limit": 35},
        },
    )
    assert job.status == JobStatus.PENDING

    # Steps 2-4: Executar LeadDiscoveryPipeline / Atualizar progresso / Finalizar Job —
    # all three happen inside this one call, entirely through the JobExecutor.
    result = await executor.execute(job)

    assert result.success is True
    assert job.status == JobStatus.FINISHED
    assert job.progress == 100
    assert job.execution_time is not None

    output = job.metadata["output"]["result"]
    assert output["total_found"] == 35
    assert output["total_valid"] == 33
    assert output["duplicates_removed"] == 4
    assert len(output["companies"]) == 29
    assert output["average_score"] == 59.66

    # The lifecycle actually went through JobEngine, in order, with progress tracked.
    logs = job_engine.list_execution_logs()
    assert [log.status for log in logs] == [
        JobStatus.PENDING,
        JobStatus.RUNNING,
        JobStatus.RUNNING,
        JobStatus.RUNNING,
        JobStatus.FINISHED,
    ]
    progress_values = [log.step for log in logs if log.step]
    assert progress_values == ["running_pipeline", "pipeline_completed"]


async def test_a_failed_pipeline_run_fails_the_job_instead_of_raising():
    job_engine = build_default_job_engine(repository=JobRepository())
    pipeline = build_default_lead_discovery_pipeline(
        providers={ResearchSource.MOCK: MockProvider(result_count=10)},
    )
    executor = PipelineJobExecutor(
        pipeline, context_factory=_context_from_job, job_engine=job_engine
    )

    # Missing the "city" the CITY strategy requires -> ValidateRequestStep rejects it,
    # LeadDiscoveryPipeline reports it as report.errors, never raises past its own
    # boundary — the executor is what turns that into a failed Job.
    job = job_engine.create(
        job_type="lead_discovery",
        metadata={"strategy": "city", "query": {}},
    )

    result = await executor.execute(job)

    assert result.success is False
    assert job.status == JobStatus.FAILED
    assert job.error_message is not None
