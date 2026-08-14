import heapq
import itertools

from app.jobs.models.enums import JobPriority
from app.jobs.models.job import Job

_PRIORITY_RANK: dict[JobPriority, int] = {
    JobPriority.LOW: 0,
    JobPriority.NORMAL: 1,
    JobPriority.HIGH: 2,
    JobPriority.CRITICAL: 3,
}


class JobQueue:
    """In-memory priority queue: higher JobPriority always dequeues before lower;
    within the same priority, FIFO (the enqueue order is preserved) — no external
    broker, this only lives as long as the process does.
    """

    def __init__(self) -> None:
        self._counter = itertools.count()
        self._heap: list[tuple[int, int, Job]] = []

    def enqueue(self, job: Job) -> None:
        # heapq is a min-heap, so rank is negated to make higher priority pop first;
        # the counter is the tie-breaker that keeps same-priority jobs in FIFO order.
        heapq.heappush(self._heap, (-_PRIORITY_RANK[job.priority], next(self._counter), job))

    def dequeue(self) -> Job | None:
        if not self._heap:
            return None
        _, _, job = heapq.heappop(self._heap)
        return job

    def peek(self) -> Job | None:
        return self._heap[0][2] if self._heap else None

    def size(self) -> int:
        return len(self._heap)
