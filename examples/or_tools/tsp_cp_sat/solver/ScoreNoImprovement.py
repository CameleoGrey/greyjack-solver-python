from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable

from ortools.sat.python import cp_model


class ScoreNoImprovement(cp_model.CpSolverSolutionCallback):
    """Log improving distances and stop search after an idle interval."""

    def __init__(
        self,
        solver: cp_model.CpSolver,
        distance: cp_model.IntVar,
        seconds: float,
        clock: Callable[[], float] = monotonic,
    ):
        super().__init__()
        self._solver = solver
        self._distance = distance
        self._seconds = seconds
        self._clock = clock
        self._lock = Lock()
        self._finished = Event()
        self._thread: Thread | None = None
        self._best_distance: int | None = None
        self._improvement_count = 0
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
        self._thread = Thread(target=self._watch, name="tsp-idle-watchdog", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._finished.set()
        if self._thread is not None:
            self._thread.join()

    def record_improvement(self, distance: int) -> None:
        with self._lock:
            if self._timed_out or (
                self._best_distance is not None and distance >= self._best_distance
            ):
                return
            self._best_distance = distance
            self._improvement_count += 1
            now = self._clock()
            self._deadline = now + self._seconds
            print(
                f"[{now - self._started_at:.3f}s] "
                f"New best solution #{self._improvement_count}: distance={distance}",
                flush=True,
            )

    def on_solution_callback(self) -> None:
        self.record_improvement(self.value(self._distance))

    def _watch(self) -> None:
        while not self._finished.wait(min(0.05, self._seconds)):
            with self._lock:
                if self._clock() >= self._deadline:
                    self._timed_out = True
                    # Retry until solve returns: the deadline can precede the
                    # native solver's installation of its stop hook.
                    self._solver.stop_search()
