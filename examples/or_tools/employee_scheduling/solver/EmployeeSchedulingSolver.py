from math import isfinite
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin.CotEmployeeSchedule import CotEmployeeSchedule
from .EmployeeSchedulingSolution import EmployeeSchedulingSolution
from .ScoreNoImprovement import ScoreNoImprovement


class EmployeeSchedulingSolver:
    def __init__(
        self,
        workers: int = 10,
        no_improvement_seconds: float = 15,
        time_limit: float | None = None,
    ):
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

    def solve(self, cotwin: CotEmployeeSchedule) -> EmployeeSchedulingSolution:
        validation_error = cotwin.model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        # Probing the dense default model can exhaust the entire idle window
        # before search produces an incumbent. Let search start promptly.
        solver.parameters.cp_model_presolve = False
        if self.time_limit is not None:
            solver.parameters.max_time_in_seconds = self.time_limit
        monitor = ScoreNoImprovement(
            solver,
            cotwin.hard_penalty,
            cotwin.soft_penalty_cents,
            self.no_improvement_seconds,
        )
        started = monotonic()
        monitor.start()
        try:
            status = solver.solve(cotwin.model, monitor)
        finally:
            monitor.close()
        elapsed = monotonic() - started

        if status in (cp_model.OPTIMAL, cp_model.INFEASIBLE, cp_model.MODEL_INVALID):
            reason = solver.status_name(status).lower()
        elif monitor.timed_out:
            reason = "no_improvement"
        elif self.time_limit is not None:
            reason = "time_limit"
        else:
            reason = "search_stopped"

        assignments = None
        hard_penalty = None
        soft_penalty_cents = None
        if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            assignments = {
                shift_id: solver.value(variable)
                for shift_id, variable in cotwin.assignment_variables.items()
            }
            hard_penalty = solver.value(cotwin.hard_penalty)
            soft_penalty_cents = solver.value(cotwin.soft_penalty_cents)
        return EmployeeSchedulingSolution(
            status=solver.status_name(status),
            assignments=assignments,
            hard_penalty=hard_penalty,
            soft_penalty_cents=soft_penalty_cents,
            elapsed_seconds=elapsed,
            termination_reason=reason,
        )
