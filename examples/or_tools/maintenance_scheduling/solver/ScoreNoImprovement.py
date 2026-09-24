from threading import Event, Lock, Thread
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin import CotMaintenanceSchedule


class ScoreNoImprovement(cp_model.CpSolverSolutionCallback):
    """Keep the best complete assignment and stop an idle CP-SAT search."""

    def __init__(
        self, solver: cp_model.CpSolver, cotwin: CotMaintenanceSchedule, seconds: float
    ) -> None:
        super().__init__()
        self._solver = solver
        self._cotwin = cotwin
        self._seconds = seconds
        self._lock = Lock()
        self._finished = Event()
        self._thread: Thread | None = None
        self._started_at = 0.0
        self._deadline = 0.0
        self._best_score: tuple[int, int] | None = None
        self._best_assignments: dict[int, tuple[int, int]] | None = None
        self._sequence = 0
        self._timed_out = False

    @property
    def best_score(self) -> tuple[int, int] | None:
        with self._lock:
            return self._best_score

    @property
    def best_assignments(self) -> dict[int, tuple[int, int]] | None:
        with self._lock:
            return self._best_assignments

    @property
    def timed_out(self) -> bool:
        with self._lock:
            return self._timed_out

    def start(self) -> None:
        with self._lock:
            self._started_at = monotonic()
            self._deadline = self._started_at + self._seconds
        self._thread = Thread(
            target=self._watch, name="maintenance-scheduling-idle-watchdog", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._finished.set()
        if self._thread is not None:
            self._thread.join()

    def on_solution_callback(self) -> None:
        score = (
            self.value(self._cotwin.hard_penalty),
            self.value(self._cotwin.soft_penalty),
        )
        with self._lock:
            if self._timed_out or (
                self._best_score is not None and score >= self._best_score
            ):
                return
            assignments = {
                job_id: (
                    self._cotwin.crew_ids[self.value(crew)],
                    self.value(self._cotwin.start_variables[job_id]),
                )
                for job_id, crew in self._cotwin.crew_variables.items()
            }
            self._best_score = score
            self._best_assignments = assignments
            self._sequence += 1
            now = monotonic()
            self._deadline = now + self._seconds
            print(
                f"[{now - self._started_at:.3f}s] New best solution "
                f"#{self._sequence}: hard_penalty={score[0]}, "
                f"soft_penalty={score[1]}",
                flush=True,
            )

    def _watch(self) -> None:
        while not self._finished.wait(min(0.05, self._seconds)):
            with self._lock:
                if monotonic() >= self._deadline:
                    self._timed_out = True
                    # Keep calling until solve returns; native setup may not have
                    # installed the solve wrapper when a short deadline expires.
                    self._solver.stop_search()
