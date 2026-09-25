"""Print each strictly improving complete VRP score during a solve."""

from threading import Lock
from time import monotonic
from typing import Callable


class BestSolutionLogger:
    def __init__(
        self,
        started_at: float,
        *,
        clock: Callable[[], float] = monotonic,
        printer: Callable[..., None] = print,
    ):
        self._started_at = started_at
        self._clock = clock
        self._printer = printer
        self._lock = Lock()
        self._best_score: tuple[int, int, int] | None = None
        self._count = 0

    def record(self, score: tuple[int, int, int]) -> bool:
        with self._lock:
            if self._best_score is not None and score >= self._best_score:
                return False
            self._best_score = score
            self._count += 1
            self._printer(
                f"[{self._clock() - self._started_at:.3f}s] "
                f"New best solution #{self._count}: "
                f"hard_penalty={score[0]}, medium_penalty={score[1]}, "
                f"distance={score[2]}",
                flush=True,
            )
            return True
