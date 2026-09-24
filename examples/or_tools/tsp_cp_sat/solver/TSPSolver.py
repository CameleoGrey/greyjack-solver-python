from math import isfinite
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin import CotTSP
from .ScoreNoImprovement import ScoreNoImprovement
from .TSPSolution import TSPSolution


class TSPSolver:
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

    def solve(self, cotwin: CotTSP) -> TSPSolution:
        validation_error = cotwin.model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        if self.time_limit is not None:
            solver.parameters.max_time_in_seconds = self.time_limit
        monitor = ScoreNoImprovement(
            solver, cotwin.distance, self.no_improvement_seconds
        )
        started = monotonic()
        monitor.start()
        try:
            status = solver.solve(cotwin.model, monitor)
        finally:
            monitor.close()
        elapsed = monotonic() - started
        status_name = solver.status_name(status)
        if status in (cp_model.OPTIMAL, cp_model.INFEASIBLE, cp_model.MODEL_INVALID):
            reason = status_name.lower()
        elif monitor.timed_out:
            reason = "no_improvement"
        elif self.time_limit is not None:
            reason = "time_limit"
        else:
            reason = "search_stopped"
        if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            return TSPSolution(status_name, None, None, elapsed, reason)
        tour_ids = self._decode_tour(cotwin, solver)
        return TSPSolution(
            status_name,
            tour_ids,
            solver.value(cotwin.distance),
            elapsed,
            reason,
        )

    @staticmethod
    def _decode_tour(cotwin: CotTSP, solver: cp_model.CpSolver) -> tuple[int, ...]:
        successors = {}
        for (source, target), variable in cotwin.arcs.items():
            if solver.value(variable):
                if source in successors:
                    raise RuntimeError("Selected arcs contain multiple successors")
                successors[source] = target
        route = []
        visited = {0}
        current = 0
        while True:
            next_index = successors.get(current)
            if next_index is None:
                raise RuntimeError("Selected tour has no successor")
            if next_index == 0:
                break
            if next_index in visited:
                raise RuntimeError("Selected tour repeats a location")
            visited.add(next_index)
            route.append(cotwin.location_ids[next_index])
            current = next_index
        if visited != set(range(len(cotwin.location_ids))):
            raise RuntimeError("Selected tour does not cover every location")
        return tuple(route)
