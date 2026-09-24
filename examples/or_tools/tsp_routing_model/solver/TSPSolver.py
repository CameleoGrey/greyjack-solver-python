import math
from time import monotonic

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from ..cotwin import CotTSP
from .TSPSolution import TSPSolution


_STATUS_NAMES = {
    value.number: value.name
    for value in routing_enums_pb2.RoutingSearchStatus.DESCRIPTOR.enum_values_by_name.values()
}


class TSPSolver:
    def __init__(
        self,
        no_improvement_seconds: float = 15,
        time_limit: float | None = None,
    ):
        for name, value in (
            ("no_improvement_seconds", no_improvement_seconds),
            ("time_limit", time_limit),
        ):
            if name == "time_limit" and value is None:
                continue
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive finite number")
            if value > 1_000_000:
                raise ValueError(f"{name} must not exceed 1,000,000 seconds")
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit

    def solve(self, cotwin: CotTSP) -> TSPSolution:
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
        best_distance: int | None = None
        improvement_count = 0
        idle_expired = False

        def on_solution() -> None:
            nonlocal best_distance, last_improvement, improvement_count
            distance = routing.CostVar().Value()
            self._check_distance(cotwin, distance)
            if best_distance is not None and distance >= best_distance:
                return
            best_distance = distance
            last_improvement = monotonic()
            improvement_count += 1
            print(
                f"[{last_improvement - started:.3f}s] "
                f"New best solution #{improvement_count}: distance={distance}",
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
        status = _STATUS_NAMES.get(
            routing.status(), f"ROUTING_STATUS_{routing.status()}"
        )
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
            return TSPSolution(status, None, None, elapsed, reason)
        tour_ids = self._decode_tour(cotwin, assignment)
        distance = assignment.ObjectiveValue()
        self._check_distance(cotwin, distance)
        return TSPSolution(status, tour_ids, distance, elapsed, reason)

    @staticmethod
    def _check_distance(cotwin: CotTSP, distance: int) -> None:
        if distance < 0 or distance > cotwin.objective_bound:
            raise RuntimeError("RoutingModel objective is outside checked bounds")

    @staticmethod
    def _decode_tour(
        cotwin: CotTSP, assignment: pywrapcp.Assignment
    ) -> tuple[int, ...]:
        routing = cotwin.routing
        manager = cotwin.manager
        seen: set[int] = set()
        tour: list[int] = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            index = assignment.Value(routing.NextVar(index))
            if routing.IsEnd(index):
                break
            location_index = manager.IndexToNode(index)
            if location_index == 0 or location_index in seen:
                raise RuntimeError("Selected tour repeats a stop or visits the depot")
            seen.add(location_index)
            tour.append(cotwin.location_ids[location_index])
            if len(tour) >= len(cotwin.location_ids):
                raise RuntimeError("Selected tour has too many stops")
        if seen != set(range(1, len(cotwin.location_ids))):
            raise RuntimeError("Selected tour does not cover every stop")
        return tuple(tour)
