import math
from time import monotonic

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from ..cotwin import CotVRP
from .VRPSolution import VRPSolution


_STATUS_NAMES = {
    value.number: value.name
    for value in routing_enums_pb2.RoutingSearchStatus.DESCRIPTOR.enum_values_by_name.values()
}


class VRPSolver:
    def __init__(
        self,
        no_improvement_seconds: float = 15,
        time_limit: float | None = 60,
    ):
        for name, value in (
            ("no_improvement_seconds", no_improvement_seconds),
            ("time_limit", time_limit),
        ):
            if value is None and name == "time_limit":
                continue
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
            if value > 1_000_000:
                raise ValueError(f"{name} must not exceed 1,000,000 seconds")
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit

    def solve(self, cotwin: CotVRP) -> VRPSolution:
        routing = cotwin.routing
        parameters = pywrapcp.DefaultRoutingSearchParameters()
        parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        if self.time_limit is not None:
            parameters.time_limit.FromMilliseconds(
                max(1, math.ceil(self.time_limit * 1000))
            )

        started = monotonic()
        last_improvement = started
        best_objective: int | None = None
        improvement_count = 0
        idle_expired = False

        def on_solution() -> None:
            nonlocal best_objective, last_improvement, improvement_count
            objective = routing.CostVar().Value()
            if best_objective is not None and objective >= best_objective:
                return
            best_objective = objective
            last_improvement = monotonic()
            improvement_count += 1
            hard, medium, distance = self._score_from_objective(cotwin, objective)
            print(
                f"[{last_improvement - started:.3f}s] "
                f"New best solution #{improvement_count}: "
                f"hard_penalty={hard}, medium_penalty={medium}, distance={distance}",
                flush=True,
            )

        def idle_limit() -> bool:
            nonlocal idle_expired
            if monotonic() - last_improvement >= self.no_improvement_seconds:
                idle_expired = True
                return True
            return False

        routing.AddAtSolutionCallback(on_solution)
        routing.AddSearchMonitor(routing.solver().CustomLimit(idle_limit))
        assignment = routing.SolveWithParameters(parameters)
        elapsed = monotonic() - started
        status = _STATUS_NAMES.get(routing.status(), f"ROUTING_STATUS_{routing.status()}")
        if idle_expired:
            reason = "no_improvement"
        elif status == "ROUTING_OPTIMAL":
            reason = "optimal"
        elif status == "ROUTING_INFEASIBLE":
            reason = "infeasible"
        elif status == "ROUTING_FAIL":
            reason = "no_solution"
        elif status == "ROUTING_INVALID":
            reason = "invalid_model"
        elif status == "ROUTING_FAIL_TIMEOUT" or (
            self.time_limit is not None and elapsed >= self.time_limit * 0.99
        ):
            reason = "time_limit"
        else:
            reason = "search_stopped"

        if assignment is None:
            return VRPSolution(status, None, None, None, None, None, elapsed, reason)
        routes = self._decode_routes(cotwin, assignment)
        objective = assignment.ObjectiveValue()
        hard, medium, distance = self._score_from_objective(cotwin, objective)
        return VRPSolution(
            status, routes, hard, medium, distance, objective, elapsed, reason
        )

    @staticmethod
    def _score_from_objective(
        cotwin: CotVRP, objective: int
    ) -> tuple[int, int, int]:
        if objective < 0 or objective > cotwin.objective_bound:
            raise RuntimeError("RoutingModel objective is outside the checked score bounds")
        if cotwin.mode == "strict":
            return 0, 0, objective
        hard, remainder = divmod(objective, cotwin.hard_weight)
        medium_units, distance = divmod(remainder, cotwin.medium_weight)
        return hard, medium_units * cotwin.time_scale, distance

    @staticmethod
    def _decode_routes(
        cotwin: CotVRP, assignment: pywrapcp.Assignment
    ) -> tuple[tuple[int, ...], ...]:
        routing = cotwin.routing
        manager = cotwin.manager
        seen: set[int] = set()
        routes: list[tuple[int, ...]] = []
        for vehicle_index in range(routing.vehicles()):
            route: list[int] = []
            index = routing.Start(vehicle_index)
            while not routing.IsEnd(index):
                index = assignment.Value(routing.NextVar(index))
                if routing.IsEnd(index):
                    break
                location_index = manager.IndexToNode(index)
                if location_index not in cotwin.customer_indices or location_index in seen:
                    raise RuntimeError("Selected routes contain a depot or repeat a customer")
                seen.add(location_index)
                route.append(cotwin.location_ids[location_index])
                if len(route) > len(cotwin.customer_indices):
                    raise RuntimeError("Selected route has too many stops")
            routes.append(tuple(route))
        if seen != cotwin.customer_indices:
            raise RuntimeError("Selected routes do not cover every customer")
        return tuple(routes)
