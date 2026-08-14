import uuid
from typing import Any

from app.jobs.models.enums import JobStatus
from app.jobs.models.job import Job


class JobRepository:
    """In-memory store of every Job — no database, same reasoning as
    app.research.repositories.ResearchResultRepository (no migration was requested for
    this module). `create`/`update` mirror the BaseRepository convention used by the
    Mission/Prospect domains (create(**attrs), update(instance, **attrs) via setattr),
    for consistency even though this isn't SQLAlchemy-backed.
    """

    def __init__(self) -> None:
        self._jobs: dict[uuid.UUID, Job] = {}

    def create(self, **attrs: Any) -> Job:
        job = Job(**attrs)
        self._jobs[job.id] = job
        return job

    def update(self, job: Job, **attrs: Any) -> Job:
        for key, value in attrs.items():
            setattr(job, key, value)
        return job

    def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        return self._jobs.get(job_id)

    def list_all(self) -> list[Job]:
        return list(self._jobs.values())

    def list_by_status(self, status: JobStatus) -> list[Job]:
        return [job for job in self._jobs.values() if job.status == status]
