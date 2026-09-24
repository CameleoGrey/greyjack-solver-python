from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable

from ortools.sat.python import cp_model


class ScoreNoImprovement(cp_model.CpSolverSolutionCallback):
    """Print strict score improvements and stop searches that have gone idle."""

    def __init__(
        self,
        solver: cp_model.CpSolver,
        hard_penalty: cp_model.IntVar,
        soft_cost: cp_model.IntVar,
        seconds: float,
        clock: Callable[[], float] = monotonic,
    ):
        super().__init__()
        self._solver = solver
        self._hard_penalty = hard_penalty
        self._soft_cost = soft_cost
        self._seconds = seconds
        self._clock = clock
        self._lock = Lock()
        self._finished = Event()
        self._thread: Thread | None = None
        self._best_score: tuple[int, int] | None = None
        self._best_solution_count = 0
        self._started_at = 0.0
        self._deadline = 0.0
        self._timed_out = False

    @property
    def timed_out(self) -> bool:
        with self._lock:
            return self._timed_out

    def start(self) -> None:
        with self._lock:
            self._started_at = self._clock()
            self._deadline = self._started_at + self._seconds
        self._thread = Thread(
            target=self._watch, name="facility-location-idle-watchdog", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._finished.set()
        if self._thread is not None:
            self._thread.join()

    def record_improvement(self, score: tuple[int, int]) -> None:
        with self._lock:
            if not self._timed_out and (
                self._best_score is None or score < self._best_score
            ):
                self._best_score = score
                now = self._clock()
                self._deadline = now + self._seconds
                self._best_solution_count += 1
                print(
                    f"[{now - self._started_at:.3f}s] "
                    f"New best solution #{self._best_solution_count}: "
                    f"hard_penalty={score[0]}, soft_cost={score[1]}",
                    flush=True,
                )

    def on_solution_callback(self) -> None:
        self.record_improvement(
            (self.value(self._hard_penalty), self.value(self._soft_cost))
        )

    def _watch(self) -> None:
        while not self._finished.wait(min(0.05, self._seconds)):
            with self._lock:
                if self._clock() >= self._deadline:
                    self._timed_out = True
                    self._solver.stop_search()
