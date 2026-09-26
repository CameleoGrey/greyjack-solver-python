"""Solve-wide incumbent logging and wall-clock idle termination."""

from datetime import timedelta
from threading import Event, Lock, Thread
from time import monotonic

from ..persistence.DomainBuilder import DomainBuilder
from .FoodPackagingSolution import FoodPackagingSolution


class ScoreNoImprovement:
    def __init__(self, cotwin, seconds: float, total_seconds: float | None):
        self.cotwin = cotwin
        self.seconds = seconds
        self.started = monotonic()
        self.total_deadline = (
            float("inf") if total_seconds is None else self.started + total_seconds
        )
        self.idle_deadline = self.started + seconds
        self.best_score = None
        self.best_routes = None
        self.best_starts = None
        self.sequence = 0
        self._active_solver = None
        self._lock = Lock()
        self._done = Event()
        self._watchdog = Thread(target=self._watch, daemon=True)
        self._watchdog.start()

    def _watch(self):
        while not self._done.wait(0.05):
            with self._lock:
                solver = self._active_solver
                expired = monotonic() >= min(self.idle_deadline, self.total_deadline)
            if expired and solver is not None:
                solver.stop_search()

    def close(self):
        self._done.set()
        self._watchdog.join()

    def activate(self, solver):
        with self._lock:
            self._active_solver = solver

    def deactivate(self, solver):
        with self._lock:
            if self._active_solver is solver:
                self._active_solver = None

    def remaining(self) -> float:
        with self._lock:
            return max(0.0, min(self.idle_deadline, self.total_deadline) - monotonic())

    def reason(self) -> str:
        now = monotonic()
        with self._lock:
            return (
                "time_limit"
                if now >= self.total_deadline
                else (
                    "no_improvement" if now >= self.idle_deadline else "search_stopped"
                )
            )

    def record(self, routes, starts) -> bool:
        """Replay before publishing; one counter covers seeds and all phases."""
        with self._lock:
            if monotonic() >= min(self.idle_deadline, self.total_deadline):
                return False
        result = FoodPackagingSolution(
            "FEASIBLE",
            {lid: tuple(route) for lid, route in routes.items()},
            {
                j: self.cotwin.origin + timedelta(minutes=value)
                for j, value in starts.items()
            },
            0,
            0,
            0,
            0.0,
            "search_stopped",
            self.cotwin.mode,
        )
        # Compute all components from business objects, then replay with them.
        domain = DomainBuilder().build_from_domain(self.cotwin.domain)
        jobs = {job.id: job for job in domain.jobs}
        for line in domain.lines:
            line.jobs.clear()
            for jid in routes[line.id]:
                job = jobs[jid]
                job.line = line
                job.start_time = result.start_times[jid]
                job.end_time = job.start_time + job.duration
                line.jobs.append(job)
        metrics = domain.calculate_metrics()
        score = (
            metrics["hard_penalty"],
            metrics["medium_penalty"],
            metrics["soft_penalty"],
        )
        if self.cotwin.mode == "strict" and not metrics["strict_feasible"]:
            raise ValueError("Strict timing candidate violates business constraints")
        result.hard_penalty, result.medium_penalty, result.soft_penalty = score
        DomainBuilder().build_from_solution(result, initial_domain=self.cotwin.domain)
        with self._lock:
            if monotonic() >= min(self.idle_deadline, self.total_deadline):
                return False
            if self.best_score is not None and score >= self.best_score:
                return False
            self.best_score = score
            self.best_routes = {lid: tuple(route) for lid, route in routes.items()}
            self.best_starts = dict(starts)
            self.sequence += 1
            elapsed = monotonic() - self.started
            self.idle_deadline = monotonic() + self.seconds
            print(
                f"[{elapsed:.3f}s] New best solution #{self.sequence}: "
                f"hard_penalty={score[0]}, medium_penalty={score[1]}, "
                f"soft_penalty={score[2]}",
                flush=True,
            )
            return True
