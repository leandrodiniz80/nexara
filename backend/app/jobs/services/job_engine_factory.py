from app.jobs.engine.job_engine import JobEngine
from app.jobs.repositories.job_repository import JobRepository


def build_default_job_engine(*, repository: JobRepository | None = None) -> JobEngine:
    """Composition root for this module. Deliberately knows nothing about what will
    actually be executed as a Job (no import of app.research, app.ai, ...) — that
    coupling belongs to whoever builds a JobExecutor for a specific pipeline, not here.
    """
    return JobEngine(repository or JobRepository())
