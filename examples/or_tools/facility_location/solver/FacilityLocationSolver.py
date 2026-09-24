from math import isfinite
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin.CotFacilityLocation import CotFacilityLocation
from .FacilityLocationSolution import FacilityLocationSolution
from .ScoreNoImprovement import ScoreNoImprovement


class FacilityLocationSolver:
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

    def solve(self, cotwin: CotFacilityLocation) -> FacilityLocationSolution:
        validation_error = cotwin.model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        if self.time_limit is not None:
            solver.parameters.max_time_in_seconds = self.time_limit
        monitor = ScoreNoImprovement(
            solver,
            cotwin.hard_penalty,
            cotwin.soft_cost,
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
        soft_cost = None
        if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            assignments = {}
            for consumer_id, row in cotwin.assignment_variables.items():
                selected = [
                    fid for fid, variable in row.items() if solver.value(variable)
                ]
                if len(selected) != 1:
                    raise RuntimeError(
                        f"Expected exactly one facility for consumer {consumer_id}"
                    )
                assignments[consumer_id] = selected[0]
            hard_penalty = solver.value(cotwin.hard_penalty)
            soft_cost = solver.value(cotwin.soft_cost)
        return FacilityLocationSolution(
            status=solver.status_name(status),
            assignments=assignments,
            hard_penalty=hard_penalty,
            soft_cost=soft_cost,
            elapsed_seconds=elapsed,
            termination_reason=reason,
            mode=cotwin.mode,
        )
