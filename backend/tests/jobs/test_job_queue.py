from app.jobs.models.enums import JobPriority
from app.jobs.models.job import Job
from app.jobs.queue.job_queue import JobQueue


def _job(priority: JobPriority) -> Job:
    return Job(job_type="lead_discovery", priority=priority)


def test_size_and_peek_on_an_empty_queue():
    queue = JobQueue()
    assert queue.size() == 0
    assert queue.peek() is None
    assert queue.dequeue() is None


def test_higher_priority_dequeues_before_lower_regardless_of_enqueue_order():
    queue = JobQueue()
    low = _job(JobPriority.LOW)
    critical = _job(JobPriority.CRITICAL)
    normal = _job(JobPriority.NORMAL)

    queue.enqueue(low)
    queue.enqueue(critical)
    queue.enqueue(normal)

    assert queue.size() == 3
    assert queue.dequeue() is critical
    assert queue.dequeue() is normal
    assert queue.dequeue() is low
    assert queue.size() == 0


def test_same_priority_jobs_dequeue_in_fifo_order():
    queue = JobQueue()
    first = _job(JobPriority.NORMAL)
    second = _job(JobPriority.NORMAL)
    third = _job(JobPriority.NORMAL)

    for job in (first, second, third):
        queue.enqueue(job)

    assert queue.dequeue() is first
    assert queue.dequeue() is second
    assert queue.dequeue() is third


def test_peek_does_not_remove_the_job():
    queue = JobQueue()
    job = _job(JobPriority.HIGH)
    queue.enqueue(job)

    assert queue.peek() is job
    assert queue.size() == 1
    assert queue.dequeue() is job
