from threading import Event, Lock, Thread
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin.CotFoodPackaging import CotFoodPackaging


class ScoreNoImprovement(cp_model.CpSolverSolutionCallback):
    """Capture lexicographically improving schedules and stop idle search."""

    def __init__(
        self,
        solver: cp_model.CpSolver,
        cotwin: CotFoodPackaging,
        seconds: float,
        initial_best: tuple | None = None,
        initial_snapshot: tuple | None = None,
        sequence: int = 0,
        elapsed_before: float = 0,
        stop_on_zero_hard: bool = False,
    ):
        super().__init__()
        self._solver = solver
        self._cotwin = cotwin
        self._seconds = seconds
        self._lock = Lock()
        self._finished = Event()
        self._thread: Thread | None = None
        self._best_score = initial_best
        self._best_snapshot = initial_snapshot
        self._sequence = sequence
        self._elapsed_before = elapsed_before
        self._stop_on_zero_hard = stop_on_zero_hard
        self._started_at = 0.0
        self._deadline = 0.0
        self._timed_out = False

    @property
    def timed_out(self) -> bool:
        with self._lock:
            return self._timed_out

    @property
    def best_score(self):
        with self._lock:
            return self._best_score

    @property
    def best_snapshot(self):
        with self._lock:
            return self._best_snapshot

    @property
    def sequence(self) -> int:
        with self._lock:
            return self._sequence

    def start(self) -> None:
        with self._lock:
            self._started_at = monotonic()
            self._deadline = self._started_at + self._seconds
        self._thread = Thread(
            target=self._watch, name="food-packaging-idle-watchdog", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._finished.set()
        if self._thread is not None:
            self._thread.join()

    def on_solution_callback(self) -> None:
        score = (
            self.value(self._cotwin.hard_penalty),
            self.value(self._cotwin.medium_penalty),
            self.value(self._cotwin.soft_penalty),
        )
        with self._lock:
            if self._timed_out or (
                self._best_score is not None and score >= self._best_score
            ):
                return
            routes = {line_id: [] for line_id in self._cotwin.line_ids}
            starts = {
                job_id: self.value(self._cotwin.start[job_id])
                for job_id in self._cotwin.job_ids
            }
            for (job_id, line_id), variable in self._cotwin.assignment.items():
                if self.value(variable):
                    routes[line_id].append(job_id)
            snapshot = (
                {
                    line_id: tuple(sorted(route, key=lambda jid: starts[jid]))
                    for line_id, route in routes.items()
                },
                starts,
            )
            self._best_score = score
            self._best_snapshot = snapshot
            self._sequence += 1
            now = monotonic()
            self._deadline = now + self._seconds
            print(
                f"[{self._elapsed_before + now - self._started_at:.3f}s] "
                f"New best solution #{self._sequence}: "
                f"hard_penalty={score[0]}, medium_penalty={score[1]}, "
                f"soft_penalty={score[2]}",
                flush=True,
            )
            if self._stop_on_zero_hard and score[0] == 0:
                self.stop_search()

    def _watch(self) -> None:
        while not self._finished.wait(min(0.05, self._seconds)):
            with self._lock:
                if monotonic() >= self._deadline:
                    self._timed_out = True
                    self._solver.stop_search()
