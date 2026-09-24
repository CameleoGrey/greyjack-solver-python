from math import isfinite
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin import CotVRP
from .ScoreNoImprovement import ScoreNoImprovement
from .VRPSolution import VRPSolution


class VRPSolver:
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
            if value is None and name == "time_limit":
                continue
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        self.workers = workers
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit

    def solve(self, cotwin: CotVRP) -> VRPSolution:
        validation_error = cotwin.model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        # Give the complete route hint a chance before dense-model presolve.
        solver.parameters.cp_model_presolve = False
        if self.time_limit is not None:
            solver.parameters.max_time_in_seconds = self.time_limit
        monitor = ScoreNoImprovement(
            solver,
            cotwin.hard_penalty,
            cotwin.medium_penalty,
            cotwin.distance,
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
        routes = None
        hard_penalty = None
        medium_penalty = None
        distance = None
        if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            routes = self._decode_routes(cotwin, solver)
            hard_penalty = solver.value(cotwin.hard_penalty)
            medium_penalty = solver.value(cotwin.medium_penalty)
            distance = solver.value(cotwin.distance)
        return VRPSolution(
            solver.status_name(status),
            routes,
            hard_penalty,
            medium_penalty,
            distance,
            elapsed,
            reason,
        )

    @staticmethod
    def _decode_routes(
        cotwin: CotVRP, solver: cp_model.CpSolver
    ) -> tuple[tuple[int, ...], ...]:
        successors: dict[tuple[int, int], int] = {}
        for (vehicle, source, target), variable in cotwin.arcs.items():
            if solver.value(variable):
                key = vehicle, source
                if key in successors:
                    raise RuntimeError("Selected arcs contain multiple successors")
                successors[key] = target
        routes = []
        visited = set()
        for vehicle, depot in enumerate(cotwin.vehicle_depots):
            route = []
            if solver.value(cotwin.used[vehicle]):
                current = depot
                while True:
                    next_index = successors.get((vehicle, current))
                    if next_index is None:
                        raise RuntimeError("Selected route has no successor")
                    if next_index == depot:
                        break
                    if next_index in visited:
                        raise RuntimeError("Selected routes repeat a customer")
                    visited.add(next_index)
                    route.append(cotwin.location_ids[next_index])
                    current = next_index
                if not route:
                    raise RuntimeError("An active vehicle has an empty route")
            routes.append(tuple(route))
        if visited != set(cotwin.customer_indices):
            raise RuntimeError("Selected routes do not cover every customer")
        return tuple(routes)
