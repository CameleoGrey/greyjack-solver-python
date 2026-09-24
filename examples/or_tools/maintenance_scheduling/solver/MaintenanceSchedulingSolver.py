from math import isfinite
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin import CotMaintenanceSchedule
from .MaintenanceSchedulingSolution import MaintenanceSchedulingSolution
from .ScoreNoImprovement import ScoreNoImprovement


class MaintenanceSchedulingSolver:
    def __init__(
        self,
        workers: int = 10,
        no_improvement_seconds: float = 30,
        time_limit: float | None = None,
    ) -> None:
        if type(workers) is not int or workers < 1:
            raise ValueError("workers must be a positive integer")
        for name, value in (
            ("no_improvement_seconds", no_improvement_seconds),
            ("time_limit", time_limit),
        ):
            if name == "time_limit" and value is None:
                continue
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        self.workers = workers
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit

    def solve(self, cotwin: CotMaintenanceSchedule) -> MaintenanceSchedulingSolution:
        validation_error = cotwin.model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        # The dense large model should enter search before the idle timer expires.
        solver.parameters.cp_model_presolve = False
        if self.time_limit is not None:
            solver.parameters.max_time_in_seconds = self.time_limit
        monitor = ScoreNoImprovement(solver, cotwin, self.no_improvement_seconds)
        started = monotonic()
        monitor.start()
        try:
            status = solver.solve(cotwin.model, monitor)
        finally:
            monitor.close()
        elapsed = monotonic() - started
        assignments = monitor.best_assignments
        score = monitor.best_score
        if assignments is not None and status not in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
        ):
            status = cp_model.FEASIBLE
        if status in (cp_model.OPTIMAL, cp_model.INFEASIBLE, cp_model.MODEL_INVALID):
            reason = solver.status_name(status).lower()
        elif monitor.timed_out:
            reason = "no_improvement"
        elif self.time_limit is not None:
            reason = "time_limit"
        else:
            reason = "search_stopped"
        return MaintenanceSchedulingSolution(
            status=solver.status_name(status),
            assignments=assignments,
            hard_penalty=None if score is None else score[0],
            soft_penalty=None if score is None else score[1],
            elapsed_seconds=elapsed,
            termination_reason=reason,
            mode=cotwin.mode,
        )
